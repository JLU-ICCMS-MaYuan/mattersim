import argparse

from pathlib import Path

from ase.io import read, write
from mattersim.forcefield import MatterSimCalculator
from mattersim.applications.relax import Relaxer
from ase.units import GPa

# 设置命令行参数解析
parser = argparse.ArgumentParser(description='Relax a structure using MatterSim.')
parser.add_argument('-i', '--input', type=str,  default="POSCAR",  help='Input structure file (e.g., POSCAR)')
parser.add_argument('-o', '--output', type=str, default="CONTCAR", help='Output structure file (e.g., CONTCAR)')
parser.add_argument('-p', '--pressure', type=float, required=True, help='Pressure in GPa for relaxation')
parser.add_argument('-s', '--symmetry', action='store_true', help='Constrain symmetry during relaxation')
parser.add_argument('-m', '--optimizer-method', type=str, default='FIRE', choices=['FIRE', 'BFGS'], help='Optimization method (FIRE or BFGS)')

args = parser.parse_args()

# 初始化计算器
# calc = MatterSimCalculator(load_path="MatterSim-v1.0.0-5M.pth", device='cuda')
calc = MatterSimCalculator(load_path="MatterSim-v1.0.0-5M.pth", device='cpu')

# 初始化 Relaxer
relaxer = Relaxer(
    optimizer=args.optimizer_method,  # 使用命令行指定的优化方法
    filter=None,  # 不使用过滤器
    constrain_symmetry=args.symmetry,  # 是否保持对称性
)

# 读取输入文件
atoms = read(args.input)
atoms.calc = calc

# 执行结构优化
converged, relaxed_structure = relaxer.relax_structures(
    atoms,
    optimizer=args.optimizer_method,   # 使用命令行指定的优化方法
    filter='EXPCELLFILTER',            # 使用指数型过滤器
    constrain_symmetry=args.symmetry,  # 是否保持对称性
    fmax=0.01,                         # 力的收敛阈值
    pressure_in_GPa=args.pressure,     # 使用命令行指定的压强
    steps=500                          # 最大优化步数
)

# 输出优化后的结构
write(args.output, relaxed_structure, format='vasp')
# print('Relaxed structure written to CONTCAR')
print(f"Cell stress = {relaxed_structure.get_stress() / GPa} GPa")    
print(f"Cell stress = {relaxed_structure.get_stress()} ") 
U  = relaxed_structure.get_total_energy()
PV = relaxed_structure.get_volume()*args.pressure*6.242e-9                   
print(f"{args.input} {args.output} {relaxed_structure.symbols} {U} {PV} {U+PV}")

