from __future__ import annotations

from dataclasses import dataclass, field

_POWER_INCREMENT = 2
_CO_INCREMENT = 1
_WINDOW = 2
_LAST_WINDOW = 8


@dataclass
class AdaptiveState:
    tick: int = 0
    new_power_limit: float = 999
    last_power_limit: float = 1000
    last_usage: int = 0
    min_co: int = 0
    prev_cpu_load: int = -1
    last_co: int = 0
    new_co: int = 0
    current_power_limit: int = 28
    last_clock: int = 0
    last_gpu_usage: int = 50
    avg_gpu_load: float = 0.0
    avg_last_gpu_load: float = 0.0
    gpu_load_samples: list = field(default_factory=list)
    gpu_last_load_samples: list = field(default_factory=list)


def update_power_limit(state, temperature, cpu_load, max_power, min_power, max_temp, is_apu):
    command = ""
    if temperature >= max_temp - 2:
        state.new_power_limit = max(min_power, state.new_power_limit - _POWER_INCREMENT)
    elif cpu_load > 10 and temperature <= max_temp - 5:
        state.new_power_limit = min(max_power, state.new_power_limit + _POWER_INCREMENT)
    if state.new_power_limit < min_power:
        state.new_power_limit = min_power
    if state.new_power_limit > max_power:
        state.new_power_limit = max_power
    if state.new_power_limit <= state.last_power_limit - 1 or state.new_power_limit >= state.last_power_limit + 1:
        if is_apu:
            tdp = int(state.new_power_limit) * 1000
            if tdp >= 5000:
                command = (
                    f"--tctl-temp={max_temp} --chtc-temp={max_temp} --apu-skin-temp={max_temp} "
                    f"--stapm-limit={tdp} --fast-limit={tdp} --stapm-time=64 --slow-limit={tdp} "
                    f"--slow-time=128 --vrm-current=300000 --vrmmax-current=300000 "
                    f"--vrmsoc-current=300000 --vrmsocmax-current=300000"
                )
                state.last_power_limit = state.new_power_limit
                state.current_power_limit = int(state.new_power_limit)
        else:
            tdp = int(state.new_power_limit) * 1000
            command = (
                f"--tctl-temp={max_temp} --ppt-limit={tdp} "
                f"--edc-limit={int(tdp * 1.33)} --tdc-limit={int(tdp * 1.33)}"
            )
            state.last_power_limit = state.new_power_limit
    state.last_usage = cpu_load
    return command


def curve_optimiser(state, cpu_load, max_co):
    if cpu_load < 10:
        new_max_co = max_co
    elif cpu_load < 80:
        new_max_co = max_co - _CO_INCREMENT * 2
    else:
        new_max_co = max_co
    if state.last_co == 0 and state.prev_cpu_load <= 0:
        state.last_co = new_max_co
    if state.prev_cpu_load < 0:
        state.prev_cpu_load = 100
    if cpu_load > state.prev_cpu_load + 10:
        state.new_co = state.last_co + _CO_INCREMENT
        state.prev_cpu_load = state.prev_cpu_load + 10
    elif cpu_load < state.prev_cpu_load - 10:
        state.new_co = state.last_co - _CO_INCREMENT
        state.prev_cpu_load = state.prev_cpu_load - 10
    if state.new_co <= state.min_co:
        state.new_co = state.min_co
    if state.new_co >= new_max_co:
        state.new_co = new_max_co
    if state.new_co > 55:
        state.new_co = 55
    if cpu_load < 5:
        state.new_co = 0
    if cpu_load > 80:
        state.new_co = max_co
    if state.new_co != state.last_co:
        state.last_co = state.new_co
        if state.new_co > 0:
            return f"--set-coall={0x100000 - state.new_co}"
        return "--set-coall=0"
    return ""


def update_igpu_clock(state, max_clock, min_clock, max_temp, temperature, current_clock,
                      gpu_load, mem_clk, cpu_clk, min_cpu_clk):
    command = ""
    if state.last_clock <= 0:
        state.last_clock = int(max_clock / 1.6)
    new_clock = current_clock
    if current_clock <= 0:
        current_clock = state.last_clock
    if state.avg_last_gpu_load <= 0:
        state.avg_last_gpu_load = gpu_load
    if state.avg_gpu_load <= 0:
        state.avg_gpu_load = gpu_load
    state.gpu_load_samples.append(gpu_load)
    if len(state.gpu_load_samples) > _WINDOW:
        oldest = state.gpu_load_samples.pop(0)
        state.avg_gpu_load = ((state.avg_gpu_load * _WINDOW) - oldest + gpu_load) / _WINDOW
    else:
        state.avg_gpu_load = ((state.avg_gpu_load * (len(state.gpu_load_samples) - 1)) + gpu_load) / len(state.gpu_load_samples)
    gpu_load = int(state.avg_gpu_load)
    if 87 <= gpu_load <= 92 and temperature <= max_temp and mem_clk >= 550 and cpu_clk > min_cpu_clk:
        new_clock = state.last_clock
    else:
        if len(state.gpu_last_load_samples) > _LAST_WINDOW:
            oldest = state.gpu_last_load_samples.pop(0)
            state.avg_last_gpu_load = ((state.avg_last_gpu_load * _LAST_WINDOW) - oldest + gpu_load) / _LAST_WINDOW
        else:
            count = len(state.gpu_last_load_samples)
            state.avg_last_gpu_load = ((state.avg_last_gpu_load * (count - 1)) + gpu_load) / count if count else gpu_load
        if int(state.avg_last_gpu_load) <= 40 and gpu_load > 60 and current_clock < 650 and cpu_clk >= min_cpu_clk and mem_clk > 550:
            new_clock = int(max_clock / 1.6)
        if gpu_load > 92 and temperature <= max_temp and mem_clk >= 550 and cpu_clk > min_cpu_clk:
            if current_clock < max_clock / 4:
                new_clock = current_clock + 75
            elif current_clock < max_clock / 3:
                new_clock = current_clock + 50
            elif current_clock < max_clock / 2:
                new_clock = current_clock + 35
            elif current_clock < max_clock / 1.33:
                new_clock = current_clock + 25
            else:
                new_clock = current_clock + 25
        elif temperature > max_temp or gpu_load < 87 or mem_clk < 550 or cpu_clk < min_cpu_clk:
            if current_clock > min_clock:
                if gpu_load > 50:
                    new_clock = current_clock - 25
                elif gpu_load < 20:
                    new_clock = current_clock - 50
    if current_clock > max_clock:
        new_clock = max_clock - 10
    if current_clock < min_clock:
        new_clock = min_clock + 10
    if (new_clock <= state.last_clock - 15 and new_clock > 0) or (new_clock >= state.last_clock + 15 and new_clock > 0):
        command = f"--gfx-clk={new_clock}"
        state.last_clock = new_clock
    state.gpu_last_load_samples.append(gpu_load)
    state.last_gpu_usage = int(gpu_load)
    return command
