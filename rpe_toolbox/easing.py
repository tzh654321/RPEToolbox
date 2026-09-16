# -*- coding: utf-8 -*-
"""时间数组与缓动曲线数学（原 RPET.py 中 time_to_float ~ interpolate_value）。

原实现中的大段说明性注释已移至 Other File/大段注释整理.md。
"""

import math
from fractions import Fraction

# 时间数组 [a, b, c] 表示 a + b/c。分母上限：
# 常规编辑用不到 192 以上，但「纵连音高」会按音高频率把音符排成很密的纵连
# （例如 120bpm 下 A4 的间隔是 1/220 拍），所以放宽到 4096 才能精确表示。
MAX_TIME_DENOMINATOR = 4096


class EasingMixin:
    # 辅助函数：时间数组处理 [beat, numerator, denominator] -> float beats
    def time_to_float(self, t_arr):
        if isinstance(t_arr, list) and len(t_arr) == 3:
            return t_arr[0] + t_arr[1] / t_arr[2]
        return float(t_arr)

    def float_to_time(self, val):
        # 输出 [a, b, c] 格式：整数拍 + 分母 <= MAX_TIME_DENOMINATOR 的最接近分数
        beat = int(val)
        remainder = val - beat
        if abs(remainder) < 1e-6:
            return [beat, 0, 1]

        # Fraction.limit_denominator 就是「分母不超过上限的最接近分数」，
        # 与原先穷举 1..192 的目标一致，但 O(log) 而不是 O(分母)。
        frac = Fraction(remainder).limit_denominator(MAX_TIME_DENOMINATOR)
        best_b, best_c = frac.numerator, frac.denominator
        if best_b == 0:
            return [beat, 0, 1]
        # 借位：b/c 可能等于 1（remainder 接近 1）
        if best_b >= best_c:
            return [beat + 1, 0, 1]
        return [beat, best_b, best_c]

    def cubic_bezier(self, t, x1, y1, x2, y2):
        # 输入 t 为时间进度，返回贝塞尔曲线上的 y（x->t 牛顿法反解）
        def sample_curve_x(t_):
            return ((3 * x1 - 3 * x2 + 1) * t_ ** 3 + (-6 * x1 + 3 * x2) * t_ ** 2 + (3 * x1) * t_)

        def sample_curve_y(t_):
            return ((3 * y1 - 3 * y2 + 1) * t_ ** 3 + (-6 * y1 + 3 * y2) * t_ ** 2 + (3 * y1) * t_)

        def sample_curve_derivative_x(t_):
            return (3 * (3 * x1 - 3 * x2 + 1) * t_ ** 2 + 2 * (-6 * x1 + 3 * x2) * t_ + 3 * x1)

        t_hat = t
        for _ in range(8):
            x_est = sample_curve_x(t_hat) - t
            dx = sample_curve_derivative_x(t_hat)
            if abs(dx) < 1e-6:
                break
            t_hat -= x_est / dx
            t_hat = max(0.0, min(1.0, t_hat))
        return sample_curve_y(t_hat)

    def _subdivide_bezier(self, x1, y1, x2, y2, t0, t1):
        """推导三次贝塞尔曲线 [t0,t1] 子段的控制点（需求十二优化）。

        先用 de Casteljau 几何细分得到子段的 x 时间映射；
        再对 y 控制点做最小二乘拟合，使子段在游戏内（x 反解求值）渲染出的
        值曲线与原曲线在该区间尽可能一致（纯几何归一化会产生大幅过冲）。
        """
        P0 = (0.0, 0.0)
        P1 = (x1, y1)
        P2 = (x2, y2)
        P3 = (1.0, 1.0)

        def lerp(a, b, t):
            return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)

        # 第 1 步：在 t1 处细分，取左侧曲线 L（覆盖 [0, t1]）
        A = lerp(P0, P1, t1)
        B = lerp(P1, P2, t1)
        C = lerp(P2, P3, t1)
        D = lerp(A, B, t1)
        E = lerp(B, C, t1)
        F = lerp(D, E, t1)
        L = [P0, A, D, F]

        # 第 2 步：在 s = t0/t1 处细分 L，取右侧曲线 Q（覆盖 [t0, t1]）
        s = t0 / t1 if t1 > 1e-12 else 0.0
        L0, L1, L2, L3 = L
        As = lerp(L0, L1, s)
        Bs = lerp(L1, L2, s)
        Cs = lerp(L2, L3, s)
        Ds = lerp(As, Bs, s)
        Es = lerp(Bs, Cs, s)
        Fs = lerp(Ds, Es, s)
        Q = [Fs, Es, Cs, L3]

        dx = Q[3][0] - Q[0][0]
        dy = Q[3][1] - Q[0][1]
        if abs(dy) < 1e-9:
            # 子段首尾值相同（常量段），曲线形状不影响结果，保留原控制点
            return [x1, y1, x2, y2]
        if abs(dx) < 1e-9:
            sx = [1.0 / 3.0, 2.0 / 3.0]
        else:
            sx = [(Q[1][0] - Q[0][0]) / dx, (Q[2][0] - Q[0][0]) / dx]

        # 在固定 x 下最小二乘拟合 y1'/y2'：目标 g(p) = 归一化的原隐函数
        def f(p):
            return self.cubic_bezier(p, x1, y1, x2, y2)

        f0 = f(t0)
        f1 = f(t1)
        span = f1 - f0
        if abs(span) < 1e-9:
            return [x1, y1, x2, y2]

        N = 21
        A11 = A12 = A22 = 0.0
        b1 = b2 = 0.0
        for i in range(N + 1):
            p = i / N
            target = (f(t0 + p * (t1 - t0)) - f0) / span
            # 在固定 x 控制点下反解 X(τ)=p
            tau = p
            for _ in range(12):
                X = 3 * (1 - tau) ** 2 * tau * sx[0] + 3 * (1 - tau) * tau ** 2 * sx[1] + tau ** 3
                dX = ((3 * (1 - tau) ** 2 - 6 * (1 - tau) * tau) * sx[0]
                      + (6 * (1 - tau) * tau - 3 * tau ** 2) * sx[1] + 3 * tau ** 2)
                if abs(dX) < 1e-9:
                    break
                tau -= (X - p) / dX
                tau = max(0.0, min(1.0, tau))
            c1 = 3 * (1 - tau) ** 2 * tau
            c2 = 3 * (1 - tau) * tau ** 2
            rhs = target - tau ** 3
            A11 += c1 * c1
            A12 += c1 * c2
            A22 += c2 * c2
            b1 += c1 * rhs
            b2 += c2 * rhs

        det = A11 * A22 - A12 * A12
        if abs(det) < 1e-12:
            sy = [1.0 / 3.0, 2.0 / 3.0]
        else:
            sy = [(b1 * A22 - b2 * A12) / det, (A11 * b2 - A12 * b1) / det]
        return [
            round(sx[0], 6),
            round(sy[0], 6),
            round(sx[1], 6),
            round(sy[1], 6),
        ]

    def apply_easing(self, t, easing_type, bezier, bezier_points):
        if t <= 0:
            return 0.0
        if t >= 1:
            return 1.0

        if bezier == 1 and isinstance(bezier_points, list) and len(bezier_points) == 4:
            x1, y1, x2, y2 = bezier_points
            return self.cubic_bezier(t, x1, y1, x2, y2)

        # 用户指定的 easingType 对应关系
        if easing_type == 1:
            return t
        if easing_type == 2:
            return math.sin((t * math.pi) / 2)
        if easing_type == 3:
            return 1 - math.cos((t * math.pi) / 2)
        if easing_type == 4:
            return 1 - (1 - t) * (1 - t)
        if easing_type == 5:
            return t ** 2
        if easing_type == 6:
            return -(math.cos(math.pi * t) - 1) / 2
        if easing_type == 7:
            return 2 * (t ** 2) if t < 0.5 else 1 - (-2 * t + 2) ** 2 / 2
        if easing_type == 8:
            return 1 - (1 - t) ** 3
        if easing_type == 9:
            return t ** 3
        if easing_type == 10:
            return 1 - (1 - t) ** 4
        if easing_type == 11:
            return t ** 4
        if easing_type == 12:
            return 4 * (t ** 3) if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2
        if easing_type == 13:
            return 8 * (t ** 4) if t < 0.5 else 1 - (-2 * t + 2) ** 4 / 2
        if easing_type == 14:
            return 1 - (1 - t) ** 5
        if easing_type == 15:
            return t ** 5
        if easing_type == 16:
            return 1 if t == 1 else 1 - 2 ** (-10 * t)
        if easing_type == 17:
            return 0 if t == 0 else 2 ** (10 * t - 10)
        if easing_type == 18:
            return math.sqrt(1 - (t - 1) ** 2)
        if easing_type == 19:
            return 1 - math.sqrt(1 - t * t)
        if easing_type == 20:
            c1 = 1.70158
            c3 = c1 + 1
            return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2
        if easing_type == 21:
            c1 = 1.70158
            c3 = c1 + 1
            return c3 * t ** 3 - c1 * t ** 2
        if easing_type == 22:
            return (1 - math.sqrt(1 - (2 * t) ** 2)) / 2 if t < 0.5 else (math.sqrt(1 - (-2 * t + 2) ** 2) + 1) / 2
        if easing_type == 23:
            c2 = 2.5949095
            if t < 0.5:
                return ((2 * t) ** 2 * ((c2 + 1) * 2 * t - c2)) / 2
            return ((2 * t - 2) ** 2 * ((c2 + 1) * (2 * t - 2) + c2) + 2) / 2
        if easing_type == 24:
            if t == 0:
                return 0
            if t == 1:
                return 1
            return 2 ** (-10 * t) * math.sin((t * 10 - 0.75) * (2 * math.pi / 3)) + 1
        if easing_type == 25:
            if t == 0:
                return 0
            if t == 1:
                return 1
            return -2 ** (10 * t - 10) * math.sin((t * 10 - 10.75) * (2 * math.pi / 3))
        if easing_type == 26:
            if t < 1 / 2.75:
                return 7.5625 * t * t
            if t < 2 / 2.75:
                t -= 1.5 / 2.75
                return 7.5625 * t * t + 0.75
            if t < 2.5 / 2.75:
                t -= 2.25 / 2.75
                return 7.5625 * t * t + 0.9375
            t -= 2.625 / 2.75
            return 7.5625 * t * t + 0.984375
        if easing_type == 27:
            return 1 - self.apply_easing(1 - t, 26, 0, [0.0, 0.0, 0.0, 0.0])
        if easing_type == 28:
            if t < 0.5:
                return (1 - self.apply_easing(1 - 2 * t, 26, 0, [0.0, 0.0, 0.0, 0.0])) / 2
            return (1 + self.apply_easing(2 * t - 1, 26, 0, [0.0, 0.0, 0.0, 0.0])) / 2
        if easing_type == 29:
            if t == 0:
                return 0
            if t == 1:
                return 1
            if t < 0.5:
                return - (2 ** (20 * t - 10)) * math.sin((20 * t - 11.125) * ((2 * math.pi) / 4.5)) / 2
            return (2 ** (-20 * t + 10)) * math.sin((20 * t - 11.125) * ((2 * math.pi) / 4.5)) / 2 + 1
        return t

    def interpolate_value(self, start, end, progress, easing_type, bezier, bezier_points):
        eased = self.apply_easing(progress, easing_type, bezier, bezier_points)
        return start + (end - start) * eased
