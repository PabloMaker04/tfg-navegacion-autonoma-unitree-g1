#!/usr/bin/env python3
"""
mujoco_ros2_lidar_bridge.py
===========================
Nodo ROS 2 que recibe el stream de LiDAR 3D simulado desde MuJoCo (vía ZMQ)
y publica:

  /lidar/points  (sensor_msgs/PointCloud2)  — nube 3D completa
  /scan          (sensor_msgs/LaserScan)    — scan 2D para SLAM/Nav2
  /odom          (nav_msgs/Odometry)
  /tf            — odom → base_link → lidar_link

Conversión 3D → 2D para /scan:
  Filtra los puntos 3D cuya altura Z (frame lidar_link) esté en
  [SCAN_Z_MIN, SCAN_Z_MAX] y proyecta al plano XY.
  Por cada bin angular (360 bins de 1°) conserva el más cercano.
  Resultado: LaserScan idéntico al que consume SLAM/Nav2, pero generado
  desde una nube 3D — detecta obstáculos a distintas alturas sin suelo/techo.

Protocolo ZMQ (puerto 5556):
  [magic: uint32][n_pts: uint32]
  [pelvis_pose: 7×float64  (x,y,z, qw,qx,qy,qz)]
  [lidar_pose:  7×float64  (x,y,z, qw,qx,qy,qz)]
  [timestamp:   float64]
  [points:      n_pts×3×float32  (XYZ en frame lidar_link)]

Uso:
  Terminal 1:  python3 run_sim_ai_g1.py
  Terminal 2:  python3 mujoco_ros2_lidar_bridge.py
  Terminal 3:  rviz2 -d rviz2/g1_mapping.rviz
"""

import struct
import math

import numpy as np
import zmq

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

from sensor_msgs.msg import PointCloud2, PointField, LaserScan
from nav_msgs.msg import Odometry
from std_msgs.msg import Header
from geometry_msgs.msg import TransformStamped
from tf2_ros import TransformBroadcaster

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
ZMQ_HOST  = "localhost"
ZMQ_PORT  = 5556
ZMQ_MAGIC = 0xDEAD1337

ODOM_FRAME  = "odom"
BASE_FRAME  = "base_link"
LIDAR_FRAME = "lidar_link"

LIDAR_TOPIC = "/lidar/points"
SCAN_TOPIC  = "/scan"
ODOM_TOPIC  = "/odom"

# Parámetros del LaserScan 2D generado desde la nube 3D
SCAN_N_BINS    = 360
SCAN_MAX_RANGE = 12.0
SCAN_MIN_RANGE = 0.15

# Banda de altura (eje Z del frame lidar_link) que contribuye al /scan.
# Ajusta si el robot detecta el suelo o el techo como obstáculos.
SCAN_Z_MIN = -0.50   # m  (cubre obstáculos a la altura de las piernas)
SCAN_Z_MAX =  0.80   # m  (cubre paredes y muebles)

SENSOR_QOS = QoSProfile(
    reliability=ReliabilityPolicy.RELIABLE,
    history=HistoryPolicy.KEEP_LAST,
    depth=5,
)


# ---------------------------------------------------------------------------
class MujocoLidarBridge(Node):

    def __init__(self):
        super().__init__("mujoco_lidar_bridge")

        self.pc_pub   = self.create_publisher(PointCloud2, LIDAR_TOPIC, SENSOR_QOS)
        self.scan_pub = self.create_publisher(LaserScan,   SCAN_TOPIC,  SENSOR_QOS)
        self.odom_pub = self.create_publisher(Odometry,    ODOM_TOPIC,  SENSOR_QOS)
        self.tf_br    = TransformBroadcaster(self)

        self._prev_pelvis = None
        self._prev_time   = None

        self._zmq_ctx  = zmq.Context()
        self._zmq_sock = self._zmq_ctx.socket(zmq.SUB)
        self._zmq_sock.connect(f"tcp://{ZMQ_HOST}:{ZMQ_PORT}")
        self._zmq_sock.setsockopt(zmq.SUBSCRIBE, b"")
        self._zmq_sock.setsockopt(zmq.RCVTIMEO, 100)

        self._timer = self.create_timer(0.05, self._poll_and_publish)

        self.get_logger().info(
            f"MujocoLidarBridge (LiDAR 3D) arrancado.\n"
            f"  ZMQ:  tcp://{ZMQ_HOST}:{ZMQ_PORT}\n"
            f"  {LIDAR_TOPIC}  — nube 3D completa\n"
            f"  {SCAN_TOPIC}   — LaserScan 2D (Z [{SCAN_Z_MIN:+.2f}, {SCAN_Z_MAX:+.2f}] m)\n"
            f"  TF: {ODOM_FRAME} → {BASE_FRAME} → {LIDAR_FRAME}"
        )

    # -----------------------------------------------------------------------
    def _poll_and_publish(self):
        try:
            raw = self._zmq_sock.recv()
        except zmq.Again:
            return

        # ── Parsear cabecera ─────────────────────────────────────────────────
        offset = 0
        if len(raw) < 8:
            self.get_logger().warn("Mensaje ZMQ demasiado corto")
            return

        magic, n_pts = struct.unpack_from("=II", raw, offset);  offset += 8
        if magic != ZMQ_MAGIC:
            self.get_logger().warn(f"Magic invalido: {magic:#010x}")
            return

        if len(raw) < offset + 56: return
        pelvis = np.frombuffer(raw, dtype=np.float64, count=7, offset=offset); offset += 56

        if len(raw) < offset + 56: return
        lidar  = np.frombuffer(raw, dtype=np.float64, count=7, offset=offset); offset += 56

        if len(raw) < offset + 8: return
        offset += 8   # timestamp

        expected = n_pts * 12
        if len(raw) < offset + expected:
            self.get_logger().warn("Mensaje incompleto")
            return

        pts = (np.frombuffer(raw, dtype=np.float32, count=n_pts * 3, offset=offset)
               .reshape(n_pts, 3) if n_pts > 0 else np.zeros((0, 3), dtype=np.float32))

        # ── Stamp y velocidades ──────────────────────────────────────────────
        ros_stamp = self.get_clock().now().to_msg()
        now_sec   = ros_stamp.sec + ros_stamp.nanosec * 1e-9

        lin_vel = np.zeros(3)
        ang_vel = np.zeros(3)
        if self._prev_pelvis is not None and self._prev_time is not None:
            dt = now_sec - self._prev_time
            if dt > 1e-6:
                lin_vel    = (pelvis[:3] - self._prev_pelvis[:3]) / dt
                q_prev_inv = self._quat_inv(self._prev_pelvis[3:7])
                q_delta    = self._quat_mul(q_prev_inv, pelvis[3:7])
                ang_vel    = 2.0 * q_delta[1:4] / dt
        self._prev_pelvis = pelvis.copy()
        self._prev_time   = now_sec

        # ── TF ──────────────────────────────────────────────────────────────
        self.tf_br.sendTransform(
            self._make_tf(ros_stamp, ODOM_FRAME, BASE_FRAME, pelvis))
        self.tf_br.sendTransform(
            self._make_tf(ros_stamp, BASE_FRAME, LIDAR_FRAME,
                          self._relative_pose(pelvis, lidar)))

        # ── Odometry ────────────────────────────────────────────────────────
        odom = Odometry()
        odom.header.stamp    = ros_stamp
        odom.header.frame_id = ODOM_FRAME
        odom.child_frame_id  = BASE_FRAME
        odom.pose.pose.position.x    = float(pelvis[0])
        odom.pose.pose.position.y    = float(pelvis[1])
        odom.pose.pose.position.z    = float(pelvis[2])
        odom.pose.pose.orientation.w = float(pelvis[3])
        odom.pose.pose.orientation.x = float(pelvis[4])
        odom.pose.pose.orientation.y = float(pelvis[5])
        odom.pose.pose.orientation.z = float(pelvis[6])
        odom.twist.twist.linear.x    = float(lin_vel[0])
        odom.twist.twist.linear.y    = float(lin_vel[1])
        odom.twist.twist.linear.z    = float(lin_vel[2])
        odom.twist.twist.angular.x   = float(ang_vel[0])
        odom.twist.twist.angular.y   = float(ang_vel[1])
        odom.twist.twist.angular.z   = float(ang_vel[2])
        self.odom_pub.publish(odom)

        # ── PointCloud2 (nube 3D completa) ──────────────────────────────────
        if n_pts > 0:
            self.pc_pub.publish(self._build_pointcloud2(ros_stamp, pts))

        # ── LaserScan 2D (aplanado por banda de altura) ─────────────────────
        self.scan_pub.publish(self._build_laserscan(ros_stamp, pts))

    # -----------------------------------------------------------------------
    # Helpers TF / quaternion
    # -----------------------------------------------------------------------
    @staticmethod
    def _make_tf(stamp, parent, child, pose):
        tf = TransformStamped()
        tf.header.stamp    = stamp
        tf.header.frame_id = parent
        tf.child_frame_id  = child
        tf.transform.translation.x = float(pose[0])
        tf.transform.translation.y = float(pose[1])
        tf.transform.translation.z = float(pose[2])
        tf.transform.rotation.w    = float(pose[3])
        tf.transform.rotation.x    = float(pose[4])
        tf.transform.rotation.y    = float(pose[5])
        tf.transform.rotation.z    = float(pose[6])
        return tf

    @staticmethod
    def _quat_inv(q):
        return np.array([q[0], -q[1], -q[2], -q[3]], dtype=np.float64)

    @staticmethod
    def _quat_mul(q1, q2):
        w1,x1,y1,z1 = q1;  w2,x2,y2,z2 = q2
        return np.array([
            w1*w2 - x1*x2 - y1*y2 - z1*z2,
            w1*x2 + x1*w2 + y1*z2 - z1*y2,
            w1*y2 - x1*z2 + y1*w2 + z1*x2,
            w1*z2 + x1*y2 - y1*x2 + z1*w2,
        ], dtype=np.float64)

    @staticmethod
    def _quat_rotate(q, v):
        qv = np.array([0., v[0], v[1], v[2]])
        qi = np.array([q[0], -q[1], -q[2], -q[3]])
        r  = MujocoLidarBridge._quat_mul(MujocoLidarBridge._quat_mul(q, qv), qi)
        return r[1:4]

    @staticmethod
    def _relative_pose(parent_pose, child_pose):
        q_pi  = MujocoLidarBridge._quat_inv(parent_pose[3:7])
        q_rel = MujocoLidarBridge._quat_mul(q_pi, child_pose[3:7])
        p_rel = MujocoLidarBridge._quat_rotate(q_pi, child_pose[:3] - parent_pose[:3])
        return np.concatenate([p_rel, q_rel])

    # -----------------------------------------------------------------------
    @staticmethod
    def _build_laserscan(stamp, pts: np.ndarray) -> LaserScan:
        """
        Convierte la nube 3D a LaserScan 2D.

        Pasos:
          1. Filtra puntos con Z en [SCAN_Z_MIN, SCAN_Z_MAX] (frame lidar_link).
          2. Proyecta X,Y al plano horizontal y calcula ángulo + distancia.
          3. Por cada bin angular de 1° conserva el punto más cercano.

        El resultado es equivalente al de un LiDAR 2D físico pero con
        información de múltiples alturas → detecta más obstáculos.
        """
        msg = LaserScan()
        msg.header.stamp    = stamp
        msg.header.frame_id = LIDAR_FRAME
        msg.angle_min       = 0.0
        msg.angle_max       = 2.0 * math.pi * (SCAN_N_BINS - 1) / SCAN_N_BINS
        msg.angle_increment = 2.0 * math.pi / SCAN_N_BINS
        msg.time_increment  = 0.0
        msg.scan_time       = 1.0 / 10.0
        msg.range_min       = float(SCAN_MIN_RANGE)
        msg.range_max       = float(SCAN_MAX_RANGE)

        ranges = [float('inf')] * SCAN_N_BINS

        if len(pts) > 0:
            # 1. Filtrar por banda de altura
            mask  = (pts[:, 2] >= SCAN_Z_MIN) & (pts[:, 2] <= SCAN_Z_MAX)
            pts2d = pts[mask]

            if len(pts2d) > 0:
                # 2. Ángulo y distancia en XY
                angles = np.arctan2(pts2d[:, 1], pts2d[:, 0]) % (2.0 * math.pi)
                dists  = np.hypot(pts2d[:, 0], pts2d[:, 1])
                bins   = np.round(angles / msg.angle_increment).astype(int) % SCAN_N_BINS

                # 3. Mínimo por bin (vectorizado)
                order = np.argsort(dists)
                for idx in order:
                    d = float(dists[idx])
                    if SCAN_MIN_RANGE < d < SCAN_MAX_RANGE:
                        b = bins[idx]
                        if d < ranges[b]:
                            ranges[b] = d

        msg.ranges      = ranges
        msg.intensities = []
        return msg

    # -----------------------------------------------------------------------
    @staticmethod
    def _build_pointcloud2(stamp, pts: np.ndarray) -> PointCloud2:
        msg = PointCloud2()
        msg.header.stamp    = stamp
        msg.header.frame_id = LIDAR_FRAME
        msg.height     = 1
        msg.width      = len(pts)
        msg.fields     = [
            PointField(name="x", offset=0,  datatype=PointField.FLOAT32, count=1),
            PointField(name="y", offset=4,  datatype=PointField.FLOAT32, count=1),
            PointField(name="z", offset=8,  datatype=PointField.FLOAT32, count=1),
        ]
        msg.is_bigendian = False
        msg.point_step   = 12
        msg.row_step     = 12 * len(pts)
        msg.data         = pts.astype(np.float32).tobytes()
        msg.is_dense     = True
        return msg

    # -----------------------------------------------------------------------
    def destroy_node(self):
        self._zmq_sock.close()
        self._zmq_ctx.term()
        super().destroy_node()


# ---------------------------------------------------------------------------
def main(args=None):
    rclpy.init(args=args)
    node = MujocoLidarBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == "__main__":
    main()
