#include <cmath>
#include <memory>
#include <optional>
#include <string>
#include <vector>

#include <Eigen/Dense>
#include <Eigen/Geometry>

#include "rclcpp/rclcpp.hpp"
#include "rclcpp/qos.hpp"
#include "sensor_msgs/msg/imu.hpp"
#include "geometry_msgs/msg/quaternion_stamped.hpp"
#include "std_msgs/msg/string.hpp"

class GravityQuaternionEstimator : public rclcpp::Node
{
public:
  GravityQuaternionEstimator()
  : Node("gravity_quaternion_estimator")
  {
    imu_topic_ = declare_parameter<std::string>("imu_topic", "/livox/imu");
    quaternion_topic_ = declare_parameter<std::string>("quaternion_topic", "/gravity_alignment/quaternion");
    status_topic_ = declare_parameter<std::string>("status_topic", "/gravity_alignment/status");
    output_frame_id_ = declare_parameter<std::string>("output_frame_id", "gravity_aligned");
    target_axis_ = declare_parameter<std::string>("target_axis", "+z");
    calibration_sample_count_ = declare_parameter<int>("calibration_sample_count", 200);
    startup_discard_samples_ = declare_parameter<int>("startup_discard_samples", 0);
    republish_period_sec_ = declare_parameter<double>("republish_period_sec", 1.0);
    input_reliability_ = declare_parameter<std::string>("input_reliability", "best_effort");

    auto sub_qos = rclcpp::SensorDataQoS();
    if (input_reliability_ == "reliable") {
      sub_qos.reliable();
    } else {
      sub_qos.best_effort();
    }

    auto latched_qos = rclcpp::QoS(rclcpp::KeepLast(1)).reliable().transient_local();
    quaternion_pub_ = create_publisher<geometry_msgs::msg::QuaternionStamped>(quaternion_topic_, latched_qos);
    status_pub_ = create_publisher<std_msgs::msg::String>(status_topic_, latched_qos);

    imu_sub_ = create_subscription<sensor_msgs::msg::Imu>(
      imu_topic_, sub_qos,
      std::bind(&GravityQuaternionEstimator::imuCallback, this, std::placeholders::_1));

    republish_timer_ = create_wall_timer(
      std::chrono::duration<double>(republish_period_sec_),
      std::bind(&GravityQuaternionEstimator::republishIfReady, this));

    publishStatus("WAITING_FOR_FIRST_IMU");
    RCLCPP_INFO(get_logger(), "GravityQuaternionEstimator started");
    RCLCPP_INFO(get_logger(), "  imu_topic: %s", imu_topic_.c_str());
    RCLCPP_INFO(get_logger(), "  quaternion_topic: %s", quaternion_topic_.c_str());
    RCLCPP_INFO(get_logger(), "  calibration_sample_count: %d", calibration_sample_count_);
    RCLCPP_INFO(get_logger(), "  startup_discard_samples: %d", startup_discard_samples_);
    RCLCPP_INFO(get_logger(), "  target_axis: %s", target_axis_.c_str());
  }

private:
  Eigen::Vector3d targetAxisVector() const
  {
    if (target_axis_ == "+x") return Eigen::Vector3d(1.0, 0.0, 0.0);
    if (target_axis_ == "-x") return Eigen::Vector3d(-1.0, 0.0, 0.0);
    if (target_axis_ == "+y") return Eigen::Vector3d(0.0, 1.0, 0.0);
    if (target_axis_ == "-y") return Eigen::Vector3d(0.0, -1.0, 0.0);
    if (target_axis_ == "-z") return Eigen::Vector3d(0.0, 0.0, -1.0);
    return Eigen::Vector3d(0.0, 0.0, 1.0);
  }

  void publishStatus(const std::string & text)
  {
    std_msgs::msg::String msg;
    msg.data = text;
    status_pub_->publish(msg);
  }

  void publishQuaternion(const rclcpp::Time & stamp)
  {
    geometry_msgs::msg::QuaternionStamped msg;
    msg.header.stamp = stamp;
    msg.header.frame_id = output_frame_id_;
    msg.quaternion.w = q_align_.w();
    msg.quaternion.x = q_align_.x();
    msg.quaternion.y = q_align_.y();
    msg.quaternion.z = q_align_.z();
    quaternion_pub_->publish(msg);
    last_quaternion_msg_ = msg;
  }

  void republishIfReady()
  {
    if (!ready_ || !last_quaternion_msg_.has_value()) {
      return;
    }
    quaternion_pub_->publish(*last_quaternion_msg_);
  }

  void imuCallback(const sensor_msgs::msg::Imu::SharedPtr msg)
  {
    const Eigen::Vector3d a(
      msg->linear_acceleration.x,
      msg->linear_acceleration.y,
      msg->linear_acceleration.z);

    if (!std::isfinite(a.x()) || !std::isfinite(a.y()) || !std::isfinite(a.z())) {
      RCLCPP_WARN_THROTTLE(get_logger(), *get_clock(), 2000, "Ignoring IMU sample with non-finite acceleration");
      return;
    }

    if (a.norm() < 1e-9) {
      RCLCPP_WARN_THROTTLE(get_logger(), *get_clock(), 2000, "Ignoring IMU sample with near-zero acceleration norm");
      return;
    }

    ++seen_imu_samples_;
    if (seen_imu_samples_ == 1) {
      RCLCPP_INFO(get_logger(), "STATE -> ACCUMULATING_GRAVITY: first IMU received");
      publishStatus("ACCUMULATING_GRAVITY");
    }

    if (ready_) {
      return;
    }

    if (seen_imu_samples_ <= static_cast<size_t>(startup_discard_samples_)) {
      return;
    }

    accel_samples_.push_back(a);

    if (accel_samples_.size() == 1) {
      RCLCPP_INFO(get_logger(), "Started averaging IMU acceleration samples");
    }

    if ((accel_samples_.size() % 20U) == 0U) {
      RCLCPP_INFO(get_logger(), "Accumulating gravity samples: %zu / %d",
        accel_samples_.size(), calibration_sample_count_);
    }

    if (static_cast<int>(accel_samples_.size()) < calibration_sample_count_) {
      return;
    }

    Eigen::Vector3d avg = Eigen::Vector3d::Zero();
    for (const auto & sample : accel_samples_) {
      avg += sample;
    }
    avg /= static_cast<double>(accel_samples_.size());

    const Eigen::Vector3d avg_normalized = avg.normalized();
    const Eigen::Vector3d target = targetAxisVector();

    q_align_ = Eigen::Quaterniond::FromTwoVectors(avg_normalized, target);
    q_align_.normalize();
    ready_ = true;

    const Eigen::Vector3d aligned_avg = q_align_ * avg_normalized;
    publishQuaternion(msg->header.stamp);
    publishStatus("READY");

    RCLCPP_INFO(get_logger(), "STATE -> READY");
    RCLCPP_INFO(get_logger(), "Gravity vector averaged from %zu IMU samples", accel_samples_.size());
    RCLCPP_INFO(get_logger(), "  avg_accel       = [%.6f, %.6f, %.6f]", avg.x(), avg.y(), avg.z());
    RCLCPP_INFO(get_logger(), "  avg_accel_norm  = %.6f", avg.norm());
    RCLCPP_INFO(get_logger(), "  avg_unit        = [%.6f, %.6f, %.6f]",
      avg_normalized.x(), avg_normalized.y(), avg_normalized.z());
    RCLCPP_INFO(get_logger(), "  aligned_unit    = [%.6f, %.6f, %.6f]",
      aligned_avg.x(), aligned_avg.y(), aligned_avg.z());
    RCLCPP_INFO(get_logger(), "  quaternion [w x y z] = [%.6f %.6f %.6f %.6f]",
      q_align_.w(), q_align_.x(), q_align_.y(), q_align_.z());
  }

  std::string imu_topic_;
  std::string quaternion_topic_;
  std::string status_topic_;
  std::string output_frame_id_;
  std::string target_axis_;
  std::string input_reliability_;

  int calibration_sample_count_{200};
  int startup_discard_samples_{0};
  double republish_period_sec_{1.0};

  bool ready_{false};
  size_t seen_imu_samples_{0};
  std::vector<Eigen::Vector3d> accel_samples_;
  Eigen::Quaterniond q_align_{Eigen::Quaterniond::Identity()};
  std::optional<geometry_msgs::msg::QuaternionStamped> last_quaternion_msg_;

  rclcpp::Subscription<sensor_msgs::msg::Imu>::SharedPtr imu_sub_;
  rclcpp::Publisher<geometry_msgs::msg::QuaternionStamped>::SharedPtr quaternion_pub_;
  rclcpp::Publisher<std_msgs::msg::String>::SharedPtr status_pub_;
  rclcpp::TimerBase::SharedPtr republish_timer_;
};

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<GravityQuaternionEstimator>());
  rclcpp::shutdown();
  return 0;
}
