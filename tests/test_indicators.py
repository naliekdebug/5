import math

from autotrader.indicators import ATR, EMA, RSI, SMA, RollingExtreme, RollingStd


def test_sma_basic():
    sma = SMA(3)
    assert sma.update(1) is None
    assert sma.update(2) is None
    assert sma.update(3) == 2.0
    assert sma.update(4) == 3.0


def test_ema_converges_to_constant():
    ema = EMA(10)
    last = None
    for _ in range(500):
        last = ema.update(50.0)
    assert last is not None
    assert abs(last - 50.0) < 1e-6


def test_ema_seed_is_sma():
    ema = EMA(5)
    vals = [10, 20, 30, 40, 50]
    out = [ema.update(v) for v in vals]
    assert out[:4] == [None, None, None, None]
    assert abs(out[4] - 30.0) < 1e-9  # seed = mean of first 5


def test_rsi_all_gains_is_100():
    rsi = RSI(14)
    val = None
    for i in range(1, 40):
        val = rsi.update(float(i))
    assert val == 100.0


def test_rsi_bounds():
    rsi = RSI(14)
    import random
    random.seed(1)
    last = None
    x = 100.0
    for _ in range(200):
        x += random.gauss(0, 1)
        last = rsi.update(x)
    assert last is not None
    assert 0.0 <= last <= 100.0


def test_atr_positive():
    atr = ATR(14)
    val = None
    price = 100.0
    for i in range(60):
        hi, lo, cl = price + 1, price - 1, price + 0.2
        val = atr.update(hi, lo, cl)
        price += 0.1
    assert val is not None
    assert val > 0


def test_rolling_extreme():
    rh = RollingExtreme(3, "max")
    rl = RollingExtreme(3, "min")
    for v in [5, 1, 3]:
        rh.update(v)
        rl.update(v)
    assert rh.value == 5
    assert rl.value == 1
    rh.update(0)
    rl.update(0)
    assert rh.value == 3  # window now [1,3,0]
    assert rl.value == 0


def test_rolling_std():
    s = RollingStd(4)
    for v in [1, 2, 3]:
        assert s.update(v) is None
    out = s.update(4)  # [1,2,3,4] sample std = sqrt(5/3)
    assert abs(out - math.sqrt(5.0 / 3.0)) < 1e-9
