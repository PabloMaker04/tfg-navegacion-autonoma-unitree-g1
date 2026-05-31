cmake_minimum_required(VERSION 3.8)
project(g1_mapping_stack)

find_package(ament_cmake REQUIRED)

install(DIRECTORY launch config description
  DESTINATION share/${PROJECT_NAME}
)

install(PROGRAMS
  scripts/record_mapping_bag.sh
  scripts/save_map.sh
  scripts/install_runtime_deps.sh
  scripts/check_runtime_deps.sh
  DESTINATION lib/${PROJECT_NAME}
)

ament_package()
