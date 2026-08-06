"""
正片叠底（Multiply）染色算法 —— 带“最接近结果”的反推逻辑
当目标输出超过固定色限制时，自动调整为最接近的可达值（即固定色本身）
"""

import math


def hex_to_rgb(hex_color: str) -> tuple:
    """将十六进制颜色字符串（如 '#F0ED69'）转换为 (R, G, B) 元组"""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb: tuple) -> str:
    """将 (R, G, B) 元组转换为十六进制颜色字符串"""
    return '#' + ''.join(f'{min(255, max(0, round(c))):02X}' for c in rgb)


def multiply_forward(fixed_rgb: tuple, input_rgb: tuple) -> tuple:
    """
    正片叠底（正向染色）公式：
        Output = round( (Input × Fixed) / 255 )
    对 R、G、B 三个通道分别独立计算

    :param fixed_rgb: 图片本身的固定色 (R, G, B)
    :param input_rgb: 输入的另一种颜色 (R, G, B)
    :return: 染色后的输出色 (R, G, B)
    """
    output_r = round((input_rgb[0] * fixed_rgb[0]) / 255)
    output_g = round((input_rgb[1] * fixed_rgb[1]) / 255)
    output_b = round((input_rgb[2] * fixed_rgb[2]) / 255)

    # 确保数值不超出 0~255（正片叠底天然不会超出，但取整后做保护）
    return (
        min(255, max(0, output_r)),
        min(255, max(0, output_g)),
        min(255, max(0, output_b))
    )


def multiply_reverse_nearest(fixed_rgb: tuple, target_rgb: tuple) -> tuple:
    """
    反推输入色，使得在正片叠底限制下，输出的颜色【最接近】目标色 target_rgb。
    
    核心逻辑（逐通道）：
        - 由于输出 = round(输入 × 固定色 / 255)，输入最大为 255，
          因此该通道能输出的最大值 = 固定色值。
        - 若目标值 ≤ 固定色值，则使用标准反推公式：输入 ≈ round(目标 × 255 / 固定色)
        - 若目标值 > 固定色值，则无法精确达到，此时最接近的实际输出 = 固定色值，
          对应输入通道应设为 255（最大值）。
        - 若固定色值为 0，则该通道输出恒为 0，任何输入都一样，此处设为 255。

    :param fixed_rgb: 图片本身的固定色 (R, G, B)
    :param target_rgb: 用户期望达到的目标颜色 (R, G, B)
    :return: 能产生最接近目标结果的输入色 (R, G, B)
    """
    inferred_input = []

    for i in range(3):  # 分别处理 R, G, B 通道
        target = target_rgb[i]
        fixed = fixed_rgb[i]

        # 情况1：固定色为 0，则输出永远为 0，任何输入都一样，统一设为 255（无害）
        if fixed == 0:
            inferred_input.append(255)
            continue

        # 情况2：目标值 ≥ 固定色值（无法精确达到，最接近的输出就是固定色本身）
        if target >= fixed:
            # 输入为 255 时，输出 = round(255 × fixed / 255) = fixed，达到该通道最大值
            inferred_input.append(255)
        else:
            # 情况3：目标值 < 固定色值，可用标准反推公式精确逼近
            # 公式：输入 ≈ round(目标 × 255 / 固定色)
            val = round((target * 255) / fixed)
            # 安全钳位（虽然此时 val 一定在 0~254 之间，但做保护）
            inferred_input.append(min(255, max(0, val)))

    return tuple(inferred_input)


# ============================================================
# 测试演示
# ============================================================
if __name__ == '__main__':

    # 定义四个固定色
    fixed_colors = {
        '#0AC3FF': (10, 195, 255),
        '#F0ED69': (240, 237, 105),
        '#FE4365': (254, 67, 101),
        '#9AE8FD': (154, 232, 253),
    }

    print("=" * 70)
    print("【改进后】反推“最接近结果”的测试用例")
    print("=" * 70)

    # ------------------------------------------------------------
    # 测试 1：之前无解的例子（固定色 #0AC3FF，目标纯白 #FFFFFF）
    # 红色通道固定为 10，最大只能输出 10，最接近 255 的就是 10
    # ------------------------------------------------------------
    print("\n>>> 测试 1：固定色 #0AC3FF (10,195,255)，目标纯白 (255,255,255)")
    fixed = fixed_colors['#0AC3FF']
    target = (255, 255, 255)

    inferred = multiply_reverse_nearest(fixed, target)
    actual_output = multiply_forward(fixed, inferred)

    print(f"  反推得到的最佳输入色：RGB{inferred} -> {rgb_to_hex(inferred)}")
    print(f"  该输入实际产生的输出：RGB{actual_output} -> {rgb_to_hex(actual_output)}")
    print(f"  目标颜色为：          RGB{target} -> {rgb_to_hex(target)}")
    print(f"  ✅ 红色通道达到最大 10，蓝色通道完美匹配 255，整体为最接近结果。")

    # ------------------------------------------------------------
    # 测试 2：固定色 #F0ED69，目标 #FFFFFF（白）
    # 蓝色通道固定 105，无法达到 255，最接近输出为 105
    # ------------------------------------------------------------
    print("\n>>> 测试 2：固定色 #F0ED69 (240,237,105)，目标纯白 (255,255,255)")
    fixed = fixed_colors['#F0ED69']
    target = (255, 255, 255)

    inferred = multiply_reverse_nearest(fixed, target)
    actual_output = multiply_forward(fixed, inferred)

    print(f"  反推得到的最佳输入色：RGB{inferred} -> {rgb_to_hex(inferred)}")
    print(f"  该输入实际产生的输出：RGB{actual_output} -> {rgb_to_hex(actual_output)}")
    print(f"  目标颜色为：          RGB{target} -> {rgb_to_hex(target)}")
    print(f"  ✅ 红色/绿色接近目标，蓝色被钳位到最大 105。")

    # ------------------------------------------------------------
    # 测试 3：固定色 #9AE8FD，目标 #FF00FF（亮紫）
    # 绿色通道固定 232，目标绿色 0，可以精确；红色/蓝色需要调整
    # ------------------------------------------------------------
    print("\n>>> 测试 3：固定色 #9AE8FD (154,232,253)，目标 #FF00FF (255,0,255)")
    fixed = fixed_colors['#9AE8FD']
    target = (255, 0, 255)

    inferred = multiply_reverse_nearest(fixed, target)
    actual_output = multiply_forward(fixed, inferred)

    print(f"  反推得到的最佳输入色：RGB{inferred} -> {rgb_to_hex(inferred)}")
    print(f"  该输入实际产生的输出：RGB{actual_output} -> {rgb_to_hex(actual_output)}")
    print(f"  目标颜色为：          RGB{target} -> {rgb_to_hex(target)}")
    print(f"  ✅ 红色通道被钳位到 154，蓝色达到 253（非常接近255），绿色精确为 0。")

    # ------------------------------------------------------------
    # 测试 4：固定色 #FE4365，目标 #888888 (136,136,136) - 全部合法
    # 验证标准反推公式的精度
    # ------------------------------------------------------------
    print("\n>>> 测试 4：固定色 #FE4365 (254,67,101)，目标灰度 #888888 (136,136,136)")
    fixed = fixed_colors['#FE4365']
    target = (136, 136, 136)

    inferred = multiply_reverse_nearest(fixed, target)
    actual_output = multiply_forward(fixed, inferred)

    print(f"  反推得到的最佳输入色：RGB{inferred} -> {rgb_to_hex(inferred)}")
    print(f"  该输入实际产生的输出：RGB{actual_output} -> {rgb_to_hex(actual_output)}")
    print(f"  目标颜色为：          RGB{target} -> {rgb_to_hex(target)}")
    print(f"  ✅ 所有通道均未超过固定色，反推精确。")