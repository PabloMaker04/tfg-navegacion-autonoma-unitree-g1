cmake_minimum_required(VERSION 3.8)
project(g1_livox_gravity_split)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(std_msgs REQUIRED)
find_package(livox_ros_driver2 REQUIRED)
find_package(Eigen3 REQUIRED)

add_executable(gravity_quaternion_estimator src/gravity_quaternion_estimator.cpp)
ament_target_dependencies(gravity_quaternion_estimator
  rclcpp sensor_msgs geometry_msgs std_msgs livox_ros_driver2)
target_link_libraries(gravity_quaternion_estimator Eigen3::Eigen)

add_executable(livox_gravity_applicator src/livox_gravity_applicator.cpp)
ament_target_dependencies(livox_gravity_applicator
  rclcpp sensor_msgs geometry_msgs std_msgs livox_ros_driver2)
target_link_libraries(livox_gravity_applicator Eigen3::Eigen)

install(TARGETS
  gravity_quaternion_estimator
  livox_gravity_applicator
  DESTINATION lib/${PROJECT_NAME})

install(DIRECTORY launch config
  DESTINATION share/${PROJECT_NAME})

ament_package()
