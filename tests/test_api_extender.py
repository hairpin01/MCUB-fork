# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Шмэлька | @hairpin01

"""
Tests for core.web.plugins.api_extender
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop

from core.web.plugins.api_extender import (
    FORBIDDEN_CONFIG_KEYS,
    ErrorCode,
    _get_pagination_params,
    _json_error,
    _json_success,
    _kernel_ready,
    _normalize_prefix,
    _paginate,
    api_aliases_delete,
    api_aliases_list,
    api_aliases_set,
    api_commands,
    api_config_get,
    api_config_set,
    api_health,
    api_meta,
    api_modules,
    api_prefix_get,
    api_prefix_set,
    api_routes,
    setup,
)


class TestNormalizePrefix:
    """Test _normalize_prefix function"""

    def test_none_uses_fallback(self):
        """Test None prefix uses fallback"""
        result = _normalize_prefix(None)
        assert result == "/api/ext"

    def test_empty_string_uses_fallback(self):
        """Test empty string uses fallback"""
        result = _normalize_prefix("")
        assert result == "/api/ext"

    def test_adds_leading_slash(self):
        """Test adds leading slash if missing"""
        result = _normalize_prefix("api/test")
        assert result == "/api/test"

    def test_strips_trailing_slash(self):
        """Test strips trailing slash"""
        result = _normalize_prefix("/api/test/")
        assert result == "/api/test"

    def test_custom_fallback(self):
        """Test custom fallback value"""
        result = _normalize_prefix(None, "/custom")
        assert result == "/custom"

    def test_slash_only_returns_slash(self):
        """Test slash-only returns slash"""
        result = _normalize_prefix("/", "/api/ext")
        assert result == "/"


class TestJsonSuccess:
    """Test _json_success function"""

    def test_basic_response(self):
        """Test basic success response"""
        response = _json_success({"key": "value"})
        assert response.status == 200
        assert response.body is not None

    def test_with_meta(self):
        """Test success response with meta"""
        meta = {"timestamp": 1234567890}
        response = _json_success({"key": "value"}, meta=meta)
        assert response.status == 200

    def test_empty_data(self):
        """Test empty data response"""
        response = _json_success({})
        assert response.status == 200


class TestJsonError:
    """Test _json_error function"""

    def test_basic_error(self):
        """Test basic error response"""
        response = _json_error("Something went wrong")
        assert response.status == 400

    def test_custom_status(self):
        """Test custom status code"""
        response = _json_error("Not found", status=404)
        assert response.status == 404

    def test_error_code(self):
        """Test error with code"""
        response = _json_error("Bad request", code=ErrorCode.MISSING_FIELD)
        assert response.status == 400

    def test_with_details(self):
        """Test error with details"""
        details = [{"field": "alias", "message": "Required"}]
        response = _json_error("Validation failed", details=details)
        assert response.status == 400


class TestGetPaginationParams:
    """Test _get_pagination_params function"""

    def test_default_values(self):
        """Test default pagination values"""
        request = MagicMock()
        request.query = {}
        page, page_size = _get_pagination_params(request)
        assert page == 1
        assert page_size == 20

    def test_custom_values(self):
        """Test custom pagination values"""
        request = MagicMock()
        request.query = {"page": "3", "pageSize": "50"}
        page, page_size = _get_pagination_params(request)
        assert page == 3
        assert page_size == 50

    def test_invalid_page_defaults_to_one(self):
        """Test invalid page defaults to 1"""
        request = MagicMock()
        request.query = {"page": "invalid"}
        page, _ = _get_pagination_params(request)
        assert page == 1

    def test_page_size_capped_at_100(self):
        """Test page size capped at 100"""
        request = MagicMock()
        request.query = {"pageSize": "200"}
        _, page_size = _get_pagination_params(request)
        assert page_size == 100

    def test_page_size_minimum_one(self):
        """Test page size minimum is 1"""
        request = MagicMock()
        request.query = {"pageSize": "0"}
        _, page_size = _get_pagination_params(request)
        assert page_size == 1


class TestPaginate:
    """Test _paginate function"""

    def test_empty_list(self):
        """Test paginate with empty list"""
        result = _paginate([], 1, 10)
        assert result["items"] == []
        assert result["meta"]["total"] == 0
        assert result["meta"]["totalPages"] == 1

    def test_single_page(self):
        """Test single page of results"""
        items = [1, 2, 3, 4, 5]
        result = _paginate(items, 1, 10)
        assert result["items"] == [1, 2, 3, 4, 5]
        assert result["meta"]["totalPages"] == 1

    def test_multiple_pages(self):
        """Test multiple pages"""
        items = list(range(25))
        result = _paginate(items, 1, 10)
        assert len(result["items"]) == 10
        assert result["meta"]["totalPages"] == 3

    def test_second_page(self):
        """Test second page results"""
        items = list(range(25))
        result = _paginate(items, 2, 10)
        assert result["items"] == [10, 11, 12, 13, 14, 15, 16, 17, 18, 19]
        assert result["meta"]["page"] == 2

    def test_page_beyond_total(self):
        """Test page beyond total pages"""
        items = [1, 2, 3]
        result = _paginate(items, 5, 10)
        assert result["meta"]["page"] == 1  # Clamped to valid page


class TestApiHealth:
    """Test api_health endpoint"""

    @pytest.mark.asyncio
    async def test_kernel_unavailable(self):
        """Test health when kernel unavailable"""
        app = web.Application()
        # Don't set kernel
        request = MagicMock()
        request.app = app
        # Call without auth decorator for unit test
        kernel, err = _kernel_ready(app)
        assert kernel is None
        assert err is not None
        assert err.status == 503

    @pytest.mark.asyncio
    async def test_success(self):
        """Test successful health check"""
        kernel = MagicMock()
        kernel.custom_prefix = "."
        kernel.VERSION = "1.0.0"

        app = web.Application()
        app["kernel"] = kernel
        app["api_extender_prefix"] = "/api/ext"

        request = MagicMock()
        request.app = app

        with patch("time.time", return_value=1234567890):
            response = await api_health(request)

        assert response.status == 200


class TestApiMeta:
    """Test api_meta endpoint"""

    @pytest.mark.asyncio
    async def test_success(self):
        """Test successful meta response"""
        kernel = MagicMock()
        kernel.VERSION = "1.0.0"
        kernel.start_time = 1000000
        kernel.loaded_modules = {"mod1": MagicMock(), "mod2": MagicMock()}
        kernel.command_handlers = {"cmd1": MagicMock(), "cmd2": MagicMock()}
        kernel.aliases = {"a": "cmd1", "b": "cmd2"}

        app = web.Application()
        app["kernel"] = kernel

        request = MagicMock()
        request.app = app

        with patch("time.time", return_value=1000100):
            response = await api_meta(request)

        assert response.status == 200


class TestApiCommands:
    """Test api_commands endpoint"""

    @pytest.mark.asyncio
    async def test_success(self):
        """Test successful commands list"""
        kernel = MagicMock()
        kernel.custom_prefix = "."
        kernel.command_handlers = {"cmd1": MagicMock(), "cmd2": MagicMock()}

        app = web.Application()
        app["kernel"] = kernel

        request = MagicMock()
        request.app = app
        request.query = {}

        response = await api_commands(request)
        assert response.status == 200

    @pytest.mark.asyncio
    async def test_with_pagination(self):
        """Test commands with pagination"""
        kernel = MagicMock()
        kernel.custom_prefix = "."
        kernel.command_handlers = {f"cmd{i}": MagicMock() for i in range(25)}

        app = web.Application()
        app["kernel"] = kernel

        request = MagicMock()
        request.app = app
        request.query = {"page": "2", "pageSize": "10"}

        response = await api_commands(request)
        assert response.status == 200


class TestApiModules:
    """Test api_modules endpoint"""

    @pytest.mark.asyncio
    async def test_success(self):
        """Test successful modules list"""
        kernel = MagicMock()
        kernel.loaded_modules = {"mod1": MagicMock(), "mod2": MagicMock()}

        app = web.Application()
        app["kernel"] = kernel

        request = MagicMock()
        request.app = app
        request.query = {}

        response = await api_modules(request)
        assert response.status == 200


class TestApiAliasesList:
    """Test api_aliases_list endpoint"""

    @pytest.mark.asyncio
    async def test_success(self):
        """Test successful aliases list"""
        kernel = MagicMock()
        kernel.aliases = {"a": "cmd1", "b": "cmd2"}

        app = web.Application()
        app["kernel"] = kernel

        request = MagicMock()
        request.app = app
        request.query = {}

        response = await api_aliases_list(request)
        assert response.status == 200


class TestApiAliasesSet:
    """Test api_aliases_set endpoint"""

    @pytest.mark.asyncio
    async def test_success(self):
        """Test successful alias creation"""
        kernel = MagicMock()
        kernel.command_handlers = {"cmd1": MagicMock()}
        kernel.aliases = {}
        kernel.config = {"aliases": {}}

        app = web.Application()
        app["kernel"] = kernel

        request = MagicMock()
        request.app = app
        request.json = AsyncMock(return_value={"alias": "a", "command": "cmd1"})

        response = await api_aliases_set(request)
        assert response.status == 200
        assert kernel.aliases["a"] == "cmd1"

    @pytest.mark.asyncio
    async def test_missing_fields(self):
        """Test missing required fields"""
        kernel = MagicMock()
        app = web.Application()
        app["kernel"] = kernel

        request = MagicMock()
        request.app = app
        request.json = AsyncMock(return_value={"alias": ""})

        response = await api_aliases_set(request)
        assert response.status == 400

    @pytest.mark.asyncio
    async def test_command_not_found(self):
        """Test command not found"""
        kernel = MagicMock()
        kernel.command_handlers = {}
        kernel.aliases = {}

        app = web.Application()
        app["kernel"] = kernel

        request = MagicMock()
        request.app = app
        request.json = AsyncMock(return_value={"alias": "a", "command": "nonexistent"})

        response = await api_aliases_set(request)
        assert response.status == 404

    @pytest.mark.asyncio
    async def test_invalid_json(self):
        """Test invalid JSON body"""
        kernel = MagicMock()
        app = web.Application()
        app["kernel"] = kernel

        request = MagicMock()
        request.app = app
        request.json = AsyncMock(side_effect=Exception("Invalid JSON"))

        response = await api_aliases_set(request)
        assert response.status == 400


class TestApiAliasesDelete:
    """Test api_aliases_delete endpoint"""

    @pytest.mark.asyncio
    async def test_success(self):
        """Test successful alias deletion"""
        kernel = MagicMock()
        kernel.aliases = {"a": "cmd1"}
        kernel.config = {"aliases": {"a": "cmd1"}}

        app = web.Application()
        app["kernel"] = kernel

        request = MagicMock()
        request.app = app
        request.match_info = {"alias": "a"}

        response = await api_aliases_delete(request)
        assert response.status == 200
        assert "a" not in kernel.aliases

    @pytest.mark.asyncio
    async def test_alias_not_found(self):
        """Test alias not found"""
        kernel = MagicMock()
        kernel.aliases = {}

        app = web.Application()
        app["kernel"] = kernel

        request = MagicMock()
        request.app = app
        request.match_info = {"alias": "nonexistent"}

        response = await api_aliases_delete(request)
        assert response.status == 404

    @pytest.mark.asyncio
    async def test_missing_alias_param(self):
        """Test missing alias parameter"""
        kernel = MagicMock()
        app = web.Application()
        app["kernel"] = kernel

        request = MagicMock()
        request.app = app
        request.match_info = {"alias": ""}

        response = await api_aliases_delete(request)
        assert response.status == 400


class TestApiPrefixGet:
    """Test api_prefix_get endpoint"""

    @pytest.mark.asyncio
    async def test_success(self):
        """Test successful prefix get"""
        kernel = MagicMock()
        kernel.custom_prefix = "!"

        app = web.Application()
        app["kernel"] = kernel

        request = MagicMock()
        request.app = app

        response = await api_prefix_get(request)
        assert response.status == 200


class TestApiPrefixSet:
    """Test api_prefix_set endpoint"""

    @pytest.mark.asyncio
    async def test_success(self):
        """Test successful prefix change"""
        kernel = MagicMock()
        kernel.custom_prefix = "."
        kernel.config = {"command_prefix": "."}

        app = web.Application()
        app["kernel"] = kernel

        request = MagicMock()
        request.app = app
        request.json = AsyncMock(return_value={"prefix": "!"})

        response = await api_prefix_set(request)
        assert response.status == 200
        assert kernel.custom_prefix == "!"

    @pytest.mark.asyncio
    async def test_missing_prefix(self):
        """Test missing prefix field"""
        kernel = MagicMock()
        app = web.Application()
        app["kernel"] = kernel

        request = MagicMock()
        request.app = app
        request.json = AsyncMock(return_value={})

        response = await api_prefix_set(request)
        assert response.status == 400


class TestApiConfigGet:
    """Test api_config_get endpoint"""

    @pytest.mark.asyncio
    async def test_success(self):
        """Test successful config get"""
        kernel = MagicMock()
        kernel.config = {"command_prefix": "!"}

        app = web.Application()
        app["kernel"] = kernel

        request = MagicMock()
        request.app = app
        request.query = {"key": "command_prefix"}

        response = await api_config_get(request)
        assert response.status == 200

    @pytest.mark.asyncio
    async def test_key_not_found(self):
        """Test config key not found"""
        kernel = MagicMock()
        kernel.config = {}

        app = web.Application()
        app["kernel"] = kernel

        request = MagicMock()
        request.app = app
        request.query = {"key": "nonexistent"}

        response = await api_config_get(request)
        assert response.status == 404

    @pytest.mark.asyncio
    async def test_missing_key_param(self):
        """Test missing key query param"""
        kernel = MagicMock()
        app = web.Application()
        app["kernel"] = kernel

        request = MagicMock()
        request.app = app
        request.query = {}

        response = await api_config_get(request)
        assert response.status == 400


class TestApiConfigSet:
    """Test api_config_set endpoint"""

    @pytest.mark.asyncio
    async def test_success_allowed_key(self):
        """Test successful config set with allowed key"""
        kernel = MagicMock()
        kernel.config = {"command_prefix": "."}

        app = web.Application()
        app["kernel"] = kernel

        request = MagicMock()
        request.app = app
        request.json = AsyncMock(return_value={"key": "command_prefix", "value": "!"})

        response = await api_config_set(request)
        assert response.status == 200
        assert kernel.config["command_prefix"] == "!"

    @pytest.mark.asyncio
    async def test_forbidden_key(self):
        """Test config set with forbidden key"""
        kernel = MagicMock()
        kernel.config = {}

        app = web.Application()
        app["kernel"] = kernel

        request = MagicMock()
        request.app = app
        request.json = AsyncMock(return_value={"key": "api_id", "value": "123"})

        response = await api_config_set(request)
        assert response.status == 403

    @pytest.mark.asyncio
    async def test_config_unavailable(self):
        """Test when config is unavailable"""
        kernel = MagicMock()
        kernel.config = None

        app = web.Application()
        app["kernel"] = kernel

        request = MagicMock()
        request.app = app
        request.json = AsyncMock(return_value={"key": "command_prefix", "value": "!"})

        response = await api_config_set(request)
        assert response.status == 500


class TestApiRoutes:
    """Test api_routes endpoint"""

    @pytest.mark.asyncio
    async def test_success(self):
        """Test successful routes list"""
        app = web.Application()
        app.router.add_get("/test", AsyncMock())

        request = MagicMock()
        request.app = app
        request.query = {}

        response = await api_routes(request)
        assert response.status == 200


class TestSetup:
    """Test setup function"""

    def test_basic_setup(self):
        """Test basic plugin setup"""
        app = web.Application()
        kernel = MagicMock()
        kernel.config = {}

        setup(app, kernel)
        assert "api_extender_prefix" in app

    def test_with_config_prefix(self):
        """Test setup with config prefix"""
        app = web.Application()
        kernel = MagicMock()
        kernel.config = {"web_api_extender": {"prefix": "/custom"}}

        setup(app, kernel)
        assert app["api_extender_prefix"] == "/custom"

    def test_with_env_prefix(self):
        """Test setup with environment prefix"""
        app = web.Application()
        kernel = MagicMock()
        kernel.config = {}

        with patch.dict("os.environ", {"MCUB_WEB_API_PREFIX": "/env"}):
            setup(app, kernel)

        assert app["api_extender_prefix"] == "/env"

    def test_env_overrides_config(self):
        """Test environment prefix overrides config"""
        app = web.Application()
        kernel = MagicMock()
        kernel.config = {"web_api_extender": {"prefix": "/config"}}

        with patch.dict("os.environ", {"MCUB_WEB_API_PREFIX": "/env"}):
            setup(app, kernel)

        assert app["api_extender_prefix"] == "/env"

    def test_v1_compatibility(self):
        """Test v1 compatibility routes are added"""
        app = web.Application()
        kernel = MagicMock()
        kernel.config = {}

        setup(app, kernel)

        # Check that routes were added
        routes = [r for r in app.router.routes()]
        paths = [r.get_info().get("path", "") for r in routes]
        # Should have both /api/ext and /api/ext/v1 routes
        assert any("/api/ext/health" in p for p in paths)
        assert any("/api/ext/v1/health" in p for p in paths)


class TestForbiddenConfigKeys:
    """Test FORBIDDEN_CONFIG_KEYS security (blacklist approach)"""

    def test_api_id_forbidden(self):
        """Test api_id is forbidden"""
        assert "api_id" in FORBIDDEN_CONFIG_KEYS

    def test_api_hash_forbidden(self):
        """Test api_hash is forbidden"""
        assert "api_hash" in FORBIDDEN_CONFIG_KEYS

    def test_phone_forbidden(self):
        """Test phone is forbidden"""
        assert "phone" in FORBIDDEN_CONFIG_KEYS

    def test_token_not_forbidden(self):
        """Test non-sensitive keys are not forbidden"""
        assert "command_prefix" not in FORBIDDEN_CONFIG_KEYS
        assert "some_random_key" not in FORBIDDEN_CONFIG_KEYS


class TestErrorCodes:
    """Test ErrorCode class"""

    def test_kernel_unavailable_code(self):
        """Test KERNEL_UNAVAILABLE error code"""
        assert ErrorCode.KERNEL_UNAVAILABLE == "KERNEL_UNAVAILABLE"

    def test_invalid_json_code(self):
        """Test INVALID_JSON error code"""
        assert ErrorCode.INVALID_JSON == "INVALID_JSON"

    def test_missing_field_code(self):
        """Test MISSING_FIELD error code"""
        assert ErrorCode.MISSING_FIELD == "MISSING_FIELD"
