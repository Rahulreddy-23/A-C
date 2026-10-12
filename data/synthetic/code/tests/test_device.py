from kestrel.alarm_latch import latched
from kestrel.infusion_motor import pulse_interval
from kestrel.sensor_pressure import occluded


def test_occlusion_boundary():
    assert not occluded(80)
    assert occluded(81)


def test_pulse_interval():
    assert pulse_interval(60, 60) == 1


def test_unsafe_alarm_cannot_clear():
    assert latched(True, True, True)
