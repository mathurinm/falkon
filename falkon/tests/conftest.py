import dataclasses
from contextlib import contextmanager

import numpy as np
import pytest
import torch
import torch.cuda as tcd

from falkon.options import BaseOptions, FalkonOptions
from falkon.utils import decide_cuda
from falkon.utils.devices import _cpu_used_mem

if decide_cuda():
    from falkon.cuda import initialization

    @pytest.fixture(scope="session", autouse=True)
    def initialize_cuda():
        # your setup code goes here, executed ahead of first test
        opt = BaseOptions(compute_arch_speed=False, use_cpu=False)
        if decide_cuda():
            initialization.init(opt)


@contextmanager
def memory_checker(opt: FalkonOptions):
    is_cpu = opt.use_cpu
    mem_check = False
    if (is_cpu and opt.max_cpu_mem < np.inf) or (not is_cpu and opt.max_gpu_mem < np.inf):
        mem_check = True

    start_ram = None
    if mem_check and not is_cpu:
        devices = list(range(torch.cuda.device_count()))
        start_ram = {}
        for dev in devices:
            tcd.reset_peak_memory_stats(dev)
            # We have to work around buggy memory stats: sometimes reset doesn't work as expected.
            start_ram[dev] = torch.cuda.max_memory_allocated(dev)
    elif mem_check:
        start_ram = _cpu_used_mem(uss=True)
        opt = dataclasses.replace(opt, max_cpu_mem=opt.max_cpu_mem + start_ram)

    yield opt

    # Check memory usage
    if mem_check and not is_cpu:
        devices = list(range(torch.cuda.device_count()))
        for dev in devices:
            used_ram = tcd.max_memory_allocated(dev) - start_ram[dev]
            assert used_ram <= opt.max_gpu_mem, \
                "DEV %d - Memory usage (%.2fMB) exceeds allowed usage (%.2fMB)" % \
                (dev, used_ram / 2 ** 20, opt.max_gpu_mem / 2 ** 20)
    elif mem_check:
        used_ram = _cpu_used_mem(uss=True) - start_ram
        assert used_ram <= opt.max_cpu_mem, \
            "Memory usage (%.2fMB) exceeds allowed usage (%.2fMB)" % \
            (used_ram / 2 ** 20, opt.max_cpu_mem / 2 ** 20)


def fix_mat(t, dtype, order, copy=False, numpy=False):
    if dtype is None or order is None:
        return None
    if isinstance(t, torch.Tensor):
        t = t.numpy()
    if isinstance(t, np.ndarray):
        t = np.array(t, dtype=dtype, order=order, copy=copy)
        if numpy:
            return t
        return torch.from_numpy(t)
    return t
