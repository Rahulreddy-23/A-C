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


def test_pressure_dwell_and_safe_acknowledgement():
    from kestrel.sensor_pressure import PressureMonitor, PressureSample, PressureState

    monitor = PressureMonitor()
    assert not monitor.evaluate(PressureSample(81, 0)).stop_output
    assert not monitor.evaluate(PressureSample(81, 2.99)).stop_output
    assert monitor.evaluate(PressureSample(81, 3)).state == PressureState.OCCLUDED
    assert not monitor.acknowledge(PressureSample(81, 4))
    assert monitor.acknowledge(PressureSample(80, 4))
    assert monitor.evaluate(None).stop_output


def test_invalid_configuration_preserves_state_and_target_stops():
    import pytest
    from kestrel.infusion_bounds import DeliveryConfiguration, DeliveryController, DeliveryMode

    controller = DeliveryController()
    valid = DeliveryConfiguration(60, 1, 120)
    controller.configure(valid)
    with pytest.raises(ValueError):
        controller.configure(DeliveryConfiguration(-1, 1, 120))
    assert controller.configuration == valid
    controller.start(sensor_safe=True, alarm_active=False)
    assert controller.tick(120, True) == 1
    assert controller.mode == DeliveryMode.STOPPED


def test_air_fault_latches_and_unsafe_acknowledgement_is_refused():
    from kestrel.sensor_air import AirMonitor

    monitor = AirMonitor(2)
    assert monitor.evaluate(None).stop_output
    assert not monitor.acknowledge(3)
    assert monitor.acknowledge(1)
