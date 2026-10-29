# Copyright 2025-2026 Arun Rajkumar
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Every board route sits behind ``boards:view`` and resolves the caller's board role.

The boards router is mounted outside the engineering workspace, so these
checks are what keep it gated: a route that forgot ``require_board`` (or
asked for too low a role, or let a write through on an archived board)
fails here.
"""

from typing import Any

from app.api.router import api_router
from app.core.permissions import WORKSPACE_ENGINEERING
from app.core.permissions_boards import BOARDS_VIEW
from app.models.board_enums import BoardMemberRole
from app.services.boards.constants import (
    BOARD_ACTION_MIN_ROLE,
    BOARD_KEY_PATTERN,
    RESERVED_BOARD_KEYS,
    BoardAction,
)
from tests.api.route_walk import ServedRoute, depends_on, served_routes

BOARD_API_MODULES = (
    "attachments",
    "boards",
    "cards",
    "checklist",
    "comments",
    "docs",
    "finder",
    "labels",
    "members",
    "prefs",
    "stages",
)
PREFIX = "/api/v1/boards"
ADMIN = BoardMemberRole.ADMIN

# Writes that don't need an active board: restoring one, and personal prefs.
WRITES_ON_ARCHIVED = frozenset(
    {
        ("POST", f"{PREFIX}/{{key}}/restore"),
        ("PUT", f"{PREFIX}/{{key}}/star"),
        ("PUT", f"{PREFIX}/{{key}}/prefs"),
    }
)
# Board settings (not card routes): admin only.
ADMIN_PATHS = ("/stages", "/teams", "/archive", "/restore")
CARD_PATHS = f"{PREFIX}/{{key}}/cards"


def board_routes() -> list[ServedRoute]:
    routes = [r for r in served_routes(api_router) if r.path.startswith(PREFIX)]
    assert len(routes) >= 50, f"only {len(routes)} board routes found"
    return routes


def board_dep(route: ServedRoute) -> Any:
    """The ``require_board`` / ``require_card`` resolver in the route's tree, if any."""
    stack = list(route.dependant.dependencies)
    while stack:
        dependency = stack.pop()
        if hasattr(dependency.call, "board_min_role"):
            return dependency.call
        stack.extend(dependency.dependencies)
    return None


def _method(route: ServedRoute) -> str:
    (method,) = route.methods
    return method


def test_every_board_route_needs_boards_view_and_not_engineering() -> None:
    for route in board_routes():
        assert depends_on(
            route, lambda c: BOARDS_VIEW in getattr(c, "required_permissions", ())
        ), route.path
        assert not depends_on(
            route, lambda c: WORKSPACE_ENGINEERING in getattr(c, "required_permissions", ())
        ), route.path


def test_the_package_modules_are_the_ones_listed() -> None:
    modules = {r.module.rsplit(".", 1)[-1] for r in board_routes()}
    assert modules == set(BOARD_API_MODULES)


def test_every_keyed_route_resolves_the_board_role() -> None:
    for route in board_routes():
        if "{key}" in route.path:
            assert board_dep(route) is not None, route.path


def test_writes_refuse_archived_boards_unless_listed() -> None:
    for route in board_routes():
        dep = board_dep(route)
        if dep is None or _method(route) == "GET":
            continue
        expected = (_method(route), route.path) not in WRITES_ON_ARCHIVED
        assert dep.board_writable is expected, route.path


def test_settings_routes_need_an_admin() -> None:
    for route in board_routes():
        dep = board_dep(route)
        if route.path.startswith(CARD_PATHS):
            continue
        settings_route = any(part in route.path for part in ADMIN_PATHS) or (
            route.path == f"{PREFIX}/{{key}}" and _method(route) == "PATCH"
        )
        member_write = "/members/" in route.path or "/labels" in route.path
        if settings_route or (member_write and _method(route) != "GET"):
            assert dep.board_min_role is ADMIN, route.path


def test_every_keyed_route_declares_its_action() -> None:
    for route in board_routes():
        dep = board_dep(route)
        if dep is None:
            continue
        assert isinstance(dep.board_action, BoardAction), route.path
        assert dep.board_min_role is BOARD_ACTION_MIN_ROLE[dep.board_action], route.path


def test_reads_are_view_and_card_writes_need_an_editor_except_comments() -> None:
    viewer, editor = BoardMemberRole.VIEWER, BoardMemberRole.EDITOR
    for route in board_routes():
        dep = board_dep(route)
        if dep is None:
            continue
        if _method(route) == "GET":
            assert dep.board_action is BoardAction.VIEW, route.path
        elif route.path.startswith(CARD_PATHS):
            expected = viewer if "/comments" in route.path else editor
            assert dep.board_min_role is expected, (route.methods, route.path)


def test_fixed_path_segments_can_never_be_a_board_key() -> None:
    fixed = {
        r.path.removeprefix(f"{PREFIX}/").split("/", 1)[0]
        for r in board_routes()
        if r.path.startswith(f"{PREFIX}/") and not r.path.startswith(f"{PREFIX}/{{")
    }
    assert {"templates", "switcher", "cards", "limits"} <= fixed
    for segment in fixed:
        key = segment.upper()
        assert key in RESERVED_BOARD_KEYS or not BOARD_KEY_PATTERN.fullmatch(key), segment
