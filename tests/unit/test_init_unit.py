"""Unit tests for the main __init__.py module."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from fastapi import FastAPI
from fastapi_pulse import add_pulse, PulseMetrics
from fastapi_pulse.constants import (
    PULSE_STATE_KEY,
    PULSE_ENDPOINT_REGISTRY_KEY,
    PULSE_PROBE_MANAGER_KEY,
    PULSE_PAYLOAD_STORE_KEY,
)


pytestmark = pytest.mark.unit


class TestAddPulse:
    """Unit tests for add_pulse function."""

    def test_add_pulse_basic(self, temp_payload_file):
        """add_pulse should initialize all components."""
        app = FastAPI()
        add_pulse(app, payload_config_path=temp_payload_file)

        assert hasattr(app.state, PULSE_STATE_KEY)
        assert hasattr(app.state, PULSE_ENDPOINT_REGISTRY_KEY)
        assert hasattr(app.state, PULSE_PROBE_MANAGER_KEY)
        assert hasattr(app.state, PULSE_PAYLOAD_STORE_KEY)

    def test_add_pulse_with_custom_metrics(self, temp_payload_file):
        """add_pulse should accept custom metrics instance."""
        app = FastAPI()
        custom_metrics = PulseMetrics(window_seconds=600)

        add_pulse(app, metrics=custom_metrics, payload_config_path=temp_payload_file)

        stored_metrics = getattr(app.state, PULSE_STATE_KEY)
        assert stored_metrics is custom_metrics
        assert stored_metrics.window_seconds == 600

    def test_add_pulse_with_metrics_factory(self, temp_payload_file):
        """add_pulse should accept metrics factory."""
        app = FastAPI()
        factory_called = []

        def factory():
            factory_called.append(True)
            return PulseMetrics(window_seconds=900)

        add_pulse(app, metrics_factory=factory, payload_config_path=temp_payload_file)

        assert len(factory_called) == 1
        stored_metrics = getattr(app.state, PULSE_STATE_KEY)
        assert stored_metrics.window_seconds == 900

    def test_add_pulse_rejects_both_metrics_and_factory(self):
        """add_pulse should reject both metrics and factory."""
        app = FastAPI()

        with pytest.raises(ValueError, match="not both"):
            add_pulse(
                app,
                metrics=PulseMetrics(),
                metrics_factory=lambda: PulseMetrics(),
            )

    def test_add_pulse_without_cors(self, temp_payload_file):
        """add_pulse should work with CORS disabled."""
        app = FastAPI()
        add_pulse(app, enable_cors=False, payload_config_path=temp_payload_file)

        assert hasattr(app.state, PULSE_STATE_KEY)

    def test_add_pulse_custom_dashboard_path(self, temp_payload_file):
        """add_pulse should accept custom dashboard path."""
        app = FastAPI()
        add_pulse(app, dashboard_path="/monitoring", payload_config_path=temp_payload_file)

        # Verify exclusion path includes custom path
        registry = getattr(app.state, PULSE_ENDPOINT_REGISTRY_KEY)
        assert "/monitoring" in registry._exclude_prefixes

    def test_add_pulse_dashboard_path_without_slash(self, temp_payload_file):
        """Dashboard path without leading slash should be normalized."""
        app = FastAPI()
        add_pulse(app, dashboard_path="monitoring", payload_config_path=temp_payload_file)

        registry = getattr(app.state, PULSE_ENDPOINT_REGISTRY_KEY)
        assert "/monitoring" in registry._exclude_prefixes

    @patch('fastapi_pulse.logger')
    def test_add_pulse_handles_missing_static_files(self, mock_logger, temp_payload_file):
        """add_pulse should handle missing static files gracefully."""
        app = FastAPI()

        with patch('fastapi_pulse.importlib.resources.files', side_effect=AttributeError("Not found")):
            with patch('fastapi_pulse.importlib.resources.path', side_effect=Exception("Not found")):
                add_pulse(app, payload_config_path=temp_payload_file)  # Should not raise

        # Should log warning
        assert mock_logger.warning.called

    def test_add_pulse_default_payload_path(self):
        """add_pulse should use default payload path when not specified."""
        app = FastAPI()
        app.root_path = "/app"

        add_pulse(app)

        payload_store = getattr(app.state, PULSE_PAYLOAD_STORE_KEY)
        assert payload_store.file_path.name == "pulse_probes.json"

    def test_add_pulse_creates_middleware(self, temp_payload_file):
        """add_pulse should add middleware to app."""
        app = FastAPI()
        initial_middleware_count = len(app.user_middleware)

        add_pulse(app, payload_config_path=temp_payload_file)

        # Should have added middleware
        assert len(app.user_middleware) > initial_middleware_count

    def test_add_pulse_includes_router(self, temp_payload_file):
        """add_pulse should include router in app."""
        app = FastAPI()
        initial_routes = len(app.routes)

        add_pulse(app, payload_config_path=temp_payload_file)

        # Should have added routes
        assert len(app.routes) > initial_routes

    def test_add_pulse_with_detailed_logging(self, temp_payload_file):
        """add_pulse should accept enable_detailed_logging parameter."""
        app = FastAPI()

        add_pulse(app, enable_detailed_logging=True, payload_config_path=temp_payload_file)

        # Should not raise
        assert hasattr(app.state, PULSE_STATE_KEY)

    def test_add_pulse_multiple_times_replaces_state(self, temp_payload_file):
        """Calling add_pulse multiple times should replace state."""
        app = FastAPI()

        add_pulse(app, metrics=PulseMetrics(window_seconds=300), payload_config_path=temp_payload_file)
        first_metrics = getattr(app.state, PULSE_STATE_KEY)

        add_pulse(app, metrics=PulseMetrics(window_seconds=600), payload_config_path=temp_payload_file)
        second_metrics = getattr(app.state, PULSE_STATE_KEY)

        assert first_metrics is not second_metrics
        assert second_metrics.window_seconds == 600
