#include <cmath>
#include <memory>
#include <optional>
#include <string>

#include <Eigen/Dense>
#include <Eigen/Geometry>

#include "rclcpp/rclcpp.hpp"
#include "rclcpp/qos.hpp"
#include "sensor_msgs/msg/imu.hpp"
#include "geometry_msgs/msg/quaternion_stamped.hpp"
#include "std_msgs/msg/string.hpp"
#include "livox_ros_driver2/msg/custom_msg.hpp"

class LivoxGravityApplicator : public rclcpp::Node
{
public:
  LivoxGravityApplicator()
  : Node("livox_gravity_applicator")
  {
    lidar_in_topic_ = declare_parameter<std::string>("lidar_in_topic", "/livox/lidar");
    imu_in_topic_ = declare_parameter<std::string>("imu_in_topic", "/livox/imu");
    quaternion_topic_ = declare_parameter<std::string>("quaternion_topic", "/gravity_alignment/quaternion");
    status_topic_ = declare_parameter<std::string>("status_topic", "/gravity_alignment/status");
    lidar_out_topic_ = declare_parameter<std::string>("lidar_out_topic", "/livox/lidar_aligned");
    imu_out_topic_ = declare_parameter<std::string>("imu_out_topic", "/livox/imu_aligned");
    output_frame_id_ = declare_parameter<std::string>("output_frame_id", "gravity_aligned");
    rotate_imu_ = declare_parameter<bool>("rotate_imu", true);
    pass_through_until_ready_ = declare_parameter<bool>("pass_through_until_ready", false);
    input_reliability_ = declare_parameter<std::string>("input_reliability", "best_effort");
    output_reliability_ = declare_parameter<std::string>("output_reliability", "reliable");
    log_every_n_clouds_ = declare_parameter<int>("log_every_n_clouds", 50);
    log_every_n_imus_ = declare_parameter<int>("log_every_n_imus", 500);
    post_roll_deg_ = declare_parameter<double>("post_roll_deg", 0.0);
    post_pitch_deg_ = declare_parameter<double>("post_pitch_deg", 0.0);
    post_yaw_deg_ = declare_parameter<double>("post_yaw_deg", 0.0);

    auto sub_qos = rclcpp::SensorDataQoS();
    if (input_reliability_ == "reliable") {
      sub_qos.reliable();
    } else {
      sub_qos.best_effort();
    }

    auto pub_qos = rclcpp::QoS(rclcpp::KeepLast(10)).durability_volatile();
    if (output_reliability_ == "best_effort") {
      pub_qos.best_effort();
    } else {
      pub_qos.reliable();
    }

    auto quat_qos = rclcpp::QoS(rclcpp::KeepLast(1)).reliable().transient_local();

    lidar_pub_ = create_publisher<livox_ros_driver2::msg::CustomMsg>(lidar_out_topic_, pub_qos);
    imu_pub_ = create_publisher<sensor_msgs::msg::Imu>(imu_out_topic_, pub_qos);
    status_pub_ = create_publisher<std_msgs::msg::String>(status_topic_, quat_qos);

    quaternion_sub_ = create_subscription<geometry_msgs::msg::QuaternionStamped>(
      quaternion_topic_, quat_qos,
      std::bind(&LivoxGravityApplicator::quaternionCallback, this, std::placeholders::_1));

    lidar_sub_ = create_subscription<livox_ros_driver2::msg::CustomMsg>(
      lidar_in_topic_, sub_qos,
      std::bind(&LivoxGravityApplicator::lidarCallback, this, std::placeholders::_1));

    imu_sub_ = create_subscription<sensor_msgs::msg::Imu>(
      imu_in_topic_, sub_qos,
      std::bind(&LivoxGravityApplicator::imuCallback, this, std::placeholders::_1));

    publishStatus("WAITING_FOR_QUATERNION");
    RCLCPP_INFO(get_logger(), "LivoxGravityApplicator started");
    RCLCPP_INFO(get_logger(), "  lidar_in_topic: %s", lidar_in_topic_.c_str());
    RCLCPP_INFO(get_logger(), "  imu_in_topic: %s", imu_in_topic_.c_str());
    RCLCPP_INFO(get_logger(), "  quaternion_topic: %s", quaternion_topic_.c_str());
    RCLCPP_INFO(get_logger(), "  lidar_out_topic: %s", lidar_out_topic_.c_str());
    RCLCPP_INFO(get_logger(), "  imu_out_topic: %s", imu_out_topic_.c_str());
    RCLCPP_INFO(get_logger(), "  rotate_imu: %s", rotate_imu_ ? "true" : "false");
    RCLCPP_INFO(get_logger(), "  post_rpy_deg: [%.3f, %.3f, %.3f]", post_roll_deg_, post_pitch_deg_, post_yaw_deg_);
  }

private:
  void publishStatus(const std::string & text)
  {
    std_msgs::msg::String msg;
    msg.data = text;
    status_pub_->publish(msg);
  }

  Eigen::Quaterniond composePostQuaternion() const
  {
    const double rr = post_roll_deg_ * M_PI / 180.0;
    const double pr = post_pitch_deg_ * M_PI / 180.0;
    const double yr = post_yaw_deg_ * M_PI / 180.0;
    const Eigen::AngleAxisd Rx(rr, Eigen::Vector3d::UnitX());
    const Eigen::AngleAxisd Ry(pr, Eigen::Vector3d::UnitY());
    const Eigen::AngleAxisd Rz(yr, Eigen::Vector3d::UnitZ());
    Eigen::Quaterniond q(Rz * Ry * Rx);
    q.normalize();
    return q;
  }

  void quaternionCallback(const geometry_msgs::msg::QuaternionStamped::SharedPtr msg)
  {
    Eigen::Quaterniond q_gravity(msg->quaternion.w, msg->quaternion.x, msg->quaternion.y, msg->quaternion.z);
    if (q_gravity.norm() < 1e-12) {
      RCLCPP_WARN(get_logger(), "Received zero quaternion. Ignoring.");
      return;
    }
    q_gravity.normalize();

    const Eigen::Quaterniond q_post = composePostQuaternion();
    const Eigen::Quaterniond q_total = q_post * q_gravity;

    q_align_ = q_total;
    ready_ = true;

    RCLCPP_INFO(get_logger(), "STATE -> READY_TO_ROTATE");
    RCLCPP_INFO(get_logger(), "Received gravity quaternion [w x y z] = [%.6f %.6f %.6f %.6f]",
      q_gravity.w(), q_gravity.x(), q_gravity.y(), q_gravity.z());
    RCLCPP_INFO(get_logger(), "Applied post quaternion [w x y z] = [%.6f %.6f %.6f %.6f]",
      q_post.w(), q_post.x(), q_post.y(), q_post.z());
    RCLCPP_INFO(get_logger(), "Using total quaternion [w x y z] = [%.6f %.6f %.6f %.6f]",
      q_align_->w(), q_align_->x(), q_align_->y(), q_align_->z());
    publishStatus("READY_TO_ROTATE");
  }

  void imuCallback(const sensor_msgs::msg::Imu::SharedPtr msg)
  {
    if (!ready_ && !pass_through_until_ready_) {
      return;
    }

    sensor_msgs::msg::Imu out = *msg;
    out.header.frame_id = output_frame_id_;

    if (ready_ && rotate_imu_) {
      const Eigen::Matrix3d R = q_align_->toRotationMatrix();

      const Eigen::Vector3d a(msg->linear_acceleration.x, msg->linear_acceleration.y, msg->linear_acceleration.z);
      const Eigen::Vector3d w(msg->angular_velocity.x, msg->angular_velocity.y, msg->angular_velocity.z);
      const Eigen::Vector3d a_rot = R * a;
      const Eigen::Vector3d w_rot = R * w;

      out.linear_acceleration.x = a_rot.x();
      out.linear_acceleration.y = a_rot.y();
      out.linear_acceleration.z = a_rot.z();
      out.angular_velocity.x = w_rot.x();
      out.angular_velocity.y = w_rot.y();
      out.angular_velocity.z = w_rot.z();

      const double qnorm2 =
        msg->orientation.x * msg->orientation.x +
        msg->orientation.y * msg->orientation.y +
        msg->orientation.z * msg->orientation.z +
        msg->orientation.w * msg->orientation.w;

      if (qnorm2 > 1e-12 && msg->orientation_covariance[0] >= 0.0) {
        Eigen::Quaterniond q_in(
          msg->orientation.w,
          msg->orientation.x,
          msg->orientation.y,
          msg->orientation.z);
        Eigen::Quaterniond q_out = (*q_align_) * q_in;
        q_out.normalize();
        out.orientation.w = q_out.w();
        out.orientation.x = q_out.x();
        out.orientation.y = q_out.y();
        out.orientation.z = q_out.z();
      }
    }

    imu_pub_->publish(out);
    ++imu_count_;
    if (!logged_first_imu_publish_) {
      logged_first_imu_publish_ = true;
      RCLCPP_INFO(get_logger(), "Started publishing corrected IMU on %s", imu_out_topic_.c_str());
    }
    if (log_every_n_imus_ > 0 && (imu_count_ % static_cast<size_t>(log_every_n_imus_) == 0U)) {
      RCLCPP_INFO(get_logger(), "Published %zu IMU messages", imu_count_);
    }
  }

  void lidarCallback(const livox_ros_driver2::msg::CustomMsg::SharedPtr msg)
  {
    if (!ready_ && !pass_through_until_ready_) {
      return;
    }

    livox_ros_driver2::msg::CustomMsg out = *msg;
    out.header.frame_id = output_frame_id_;

    if (ready_) {
      const Eigen::Matrix3d R = q_align_->toRotationMatrix();
      for (auto & pt : out.points) {
        const Eigen::Vector3d p(pt.x, pt.y, pt.z);
        const Eigen::Vector3d pr = R * p;
        pt.x = static_cast<float>(pr.x());
        pt.y = static_cast<float>(pr.y());
        pt.z = static_cast<float>(pr.z());
      }
    }

    lidar_pub_->publish(out);
    ++lidar_count_;
    if (!logged_first_lidar_publish_) {
      logged_first_lidar_publish_ = true;
      RCLCPP_INFO(get_logger(), "Started publishing corrected Livox clouds on %s", lidar_out_topic_.c_str());
    }
    if (log_every_n_clouds_ > 0 && (lidar_count_ % static_cast<size_t>(log_every_n_clouds_) == 0U)) {
      RCLCPP_INFO(get_logger(), "Published %zu aligned Livox cloud messages", lidar_count_);
    }
  }

  std::string lidar_in_topic_;
  std::string imu_in_topic_;
  std::string quaternion_topic_;
  std::string status_topic_;
  std::string lidar_out_topic_;
  std::string imu_out_topic_;
  std::string output_frame_id_;
  std::string input_reliability_;
  std::string output_reliability_;

  bool rotate_imu_{true};
  bool pass_through_until_ready_{false};
  bool ready_{false};
  bool logged_first_lidar_publish_{false};
  bool logged_first_imu_publish_{false};

  int log_every_n_clouds_{50};
  int log_every_n_imus_{500};
  double post_roll_deg_{0.0};
  double post_pitch_deg_{0.0};
  double post_yaw_deg_{0.0};
  size_t lidar_count_{0};
  size_t imu_count_{0};

  std::optional<Eigen::Quaterniond> q_align_;

  rclcpp::Subscription<livox_ros_driver2::msg::CustomMsg>::SharedPtr lidar_sub_;
  rclcpp::Subscription<sensor_msgs::msg::Imu>::SharedPtr imu_sub_;
  rclcpp::Subscription<geometry_msgs::msg::QuaternionStamped>::SharedPtr quaternion_sub_;
  rclcpp::Publisher<livox_ros_driver2::msg::CustomMsg>::SharedPtr lidar_pub_;
  rclcpp::Publisher<sensor_msgs::msg::Imu>::SharedPtr imu_pub_;
  rclcpp::Publisher<std_msgs::msg::String>::SharedPtr status_pub_;
};

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<LivoxGravityApplicator>());
  rclcpp::shutdown();
  return 0;
}
