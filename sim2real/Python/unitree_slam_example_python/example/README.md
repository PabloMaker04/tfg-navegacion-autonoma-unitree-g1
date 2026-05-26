# unitree_slam_example — Python

Clon Python exacto de `unitree_slam_example_c++`.

### Run

```bash
# Mirrors: ./keyDemo eth0
python3 example/src/keyDemo.py enp2s0
```

### RViz2

```bash
# Durante el mapeo
rviz2 -d rviz2/mapping.rviz

# Durante la navegación
rviz2 -d rviz2/relocation.rviz
```

### Keys (idénticas al C++)

| Tecla | Acción |
|-------|--------|
| `q` | Start mapping |
| `w` | End mapping → guarda `/home/unitree/test.pcd` |
| `a` | Start relocation |
| `s` | Add current pose to task list |
| `d` | Execute task list (bucle) |
| `f` | Clear task list |
| `z` | Pause navigation |
| `x` | Resume navigation |
| cualquier otra | Stop SLAM |
| `Ctrl+C` | Salir |
