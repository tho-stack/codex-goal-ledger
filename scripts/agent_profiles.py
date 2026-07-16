#!/usr/bin/env python3
"""Canonical Goal Ledger-owned agent profile manifest."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentProfile:
    name: str
    model: str
    effort: str
    label: str
    purpose: str

    @property
    def requested_profile(self) -> str:
        return f"{self.model} {self.effort}"


IMPLEMENTER_PROFILES = (
    AgentProfile(
        "goal-ledger-implementer",
        "gpt-5.6-luna",
        "max",
        "Luna Max",
        "default implementation lane",
    ),
    AgentProfile(
        "goal-ledger-implementer-luna-high",
        "gpt-5.6-luna",
        "high",
        "Luna High",
        "routine or latency-sensitive implementation",
    ),
    AgentProfile(
        "goal-ledger-implementer-terra-ultra",
        "gpt-5.6-terra",
        "ultra",
        "Terra Ultra",
        "balanced implementation with deeper reasoning",
    ),
    AgentProfile(
        "goal-ledger-implementer-sol-medium",
        "gpt-5.6-sol",
        "medium",
        "Sol Medium",
        "frontier implementation at moderate reasoning effort",
    ),
    AgentProfile(
        "goal-ledger-implementer-sol-xhigh",
        "gpt-5.6-sol",
        "xhigh",
        "Sol XHigh",
        "difficult implementation requiring stronger reasoning",
    ),
    AgentProfile(
        "goal-ledger-implementer-sol-ultra",
        "gpt-5.6-sol",
        "ultra",
        "Sol Ultra",
        "highest-scrutiny implementation lane",
    ),
)
REVIEWER_PROFILES = (
    AgentProfile(
        "goal-ledger-gate-reviewer",
        "gpt-5.6-luna",
        "high",
        "Luna High gate reviewer",
        "fast independent read-only operational gate review",
    ),
    AgentProfile(
        "goal-ledger-reviewer",
        "gpt-5.6-sol",
        "xhigh",
        "Sol XHigh reviewer",
        "independent read-only closeout review",
    ),
)
AGENT_PROFILES = IMPLEMENTER_PROFILES + REVIEWER_PROFILES
PROFILE_BY_NAME = {profile.name: profile for profile in AGENT_PROFILES}
IMPLEMENTER_BY_NAME = {profile.name: profile for profile in IMPLEMENTER_PROFILES}
AGENT_NAMES = tuple(profile.name for profile in AGENT_PROFILES)
IMPLEMENTER_NAMES = tuple(profile.name for profile in IMPLEMENTER_PROFILES)
DEFAULT_IMPLEMENTER = IMPLEMENTER_PROFILES[0]
