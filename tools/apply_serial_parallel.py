from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def replace_regex_once(text: str, pattern: str, replacement: str, label: str) -> str:
    new_text, count = re.subn(pattern, replacement, text, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one regex match, found {count}")
    return new_text


# ---------------------------------------------------------------------------
# Backend model
# ---------------------------------------------------------------------------
path = ROOT / "custom_components/smart_sprinkler_control/models/zone.py"
text = path.read_text()
text = replace_once(
    text,
    "    # Zone durations (zone_id -> duration in minutes)\n"
    "    zone_durations: Dict[int, int] = field(default_factory=dict)\n\n"
    "    # Weather conditions\n",
    "    # Zone durations (zone_id -> duration in minutes)\n"
    "    zone_durations: Dict[int, int] = field(default_factory=dict)\n\n"
    "    # Execution settings. Existing schedules default to serial mode.\n"
    "    execution_mode: str = \"serial\"  # serial | parallel\n"
    "    zone_delay_seconds: int = 5\n\n"
    "    # Weather conditions\n",
    "schedule model fields",
)
text = replace_once(
    text,
    "    def start_zone(\n"
    "        self, zone_id: int, duration: int, schedule_id: Optional[str] = None\n"
    "    ) -> bool:\n"
    "        \"\"\"Start a specific zone.\n\n"
    "        Only one zone can run at a time to maintain water pressure.\n"
    "        Starting a new zone will automatically stop any currently running zone.\n"
    "        \"\"\"\n",
    "    def start_zone(\n"
    "        self,\n"
    "        zone_id: int,\n"
    "        duration: int,\n"
    "        schedule_id: Optional[str] = None,\n"
    "        allow_parallel: bool = False,\n"
    "    ) -> bool:\n"
    "        \"\"\"Start a specific zone.\n\n"
    "        By default the legacy single-zone behaviour is preserved. Scheduled\n"
    "        programs in parallel mode pass ``allow_parallel=True`` so selected\n"
    "        zones may run at the same time.\n"
    "        \"\"\"\n",
    "start_zone signature",
)
text = replace_once(
    text,
    "        # Single-zone operation: stop any currently running zone first\n"
    "        active_zones = self.get_active_zones()\n"
    "        if active_zones:\n"
    "            for active_zone in active_zones:\n"
    "                _LOGGER.debug(\n"
    "                    \"Stopping zone %d to start zone %d (single-zone operation)\",\n"
    "                    active_zone.zone_id,\n"
    "                    zone_id,\n"
    "                )\n"
    "                active_zone.stop_watering()\n",
    "        # Legacy/manual serial operation stops another active zone. Parallel\n"
    "        # schedules explicitly opt out and keep all selected zones active.\n"
    "        if not allow_parallel:\n"
    "            active_zones = self.get_active_zones()\n"
    "            if active_zones:\n"
    "                for active_zone in active_zones:\n"
    "                    _LOGGER.debug(\n"
    "                        \"Stopping zone %d to start zone %d (serial operation)\",\n"
    "                        active_zone.zone_id,\n"
    "                        zone_id,\n"
    "                    )\n"
    "                    active_zone.stop_watering()\n",
    "parallel start behaviour",
)
path.write_text(text)


# ---------------------------------------------------------------------------
# Integration backend
# ---------------------------------------------------------------------------
path = ROOT / "custom_components/smart_sprinkler_control/__init__.py"
text = path.read_text()
text = replace_once(
    text,
    "        vol.Optional(\"zone_durations\"): dict,\n"
    "        vol.Optional(\"enabled\", default=True): cv.boolean,\n",
    "        vol.Optional(\"zone_durations\"): dict,\n"
    "        vol.Optional(\"execution_mode\", default=\"serial\"): vol.In(\n"
    "            [\"serial\", \"parallel\"]\n"
    "        ),\n"
    "        vol.Optional(\"zone_delay_seconds\", default=5): vol.All(\n"
    "            vol.Coerce(int), vol.Range(min=0, max=3600)\n"
    "        ),\n"
    "        vol.Optional(\"enabled\", default=True): cv.boolean,\n",
    "service schema",
)
text = replace_once(
    text,
    "                        zone_durations=zone_durations,\n"
    "                        skip_if_rain=schedule_data.get(\"skip_if_rain\", True),\n",
    "                        zone_durations=zone_durations,\n"
    "                        execution_mode=schedule_data.get(\"execution_mode\", \"serial\"),\n"
    "                        zone_delay_seconds=int(\n"
    "                            schedule_data.get(\"zone_delay_seconds\", 5)\n"
    "                        ),\n"
    "                        skip_if_rain=schedule_data.get(\"skip_if_rain\", True),\n",
    "restore schedule fields",
)
# Persist new settings next to zone_durations in the schedule storage mapping.
text = replace_regex_once(
    text,
    r'(\"zone_durations\":\s*schedule\.zone_durations,\n)(\s*\"skip_if_rain\":)',
    r'\1                "execution_mode": schedule.execution_mode,\n                "zone_delay_seconds": schedule.zone_delay_seconds,\n\2',
    "persist schedule fields",
)
text = replace_once(
    text,
    "            zone_durations=call.data.get(\"zone_durations\", {}),\n"
    "            enabled=call.data.get(\"enabled\", True),\n",
    "            zone_durations=call.data.get(\"zone_durations\", {}),\n"
    "            execution_mode=call.data.get(\"execution_mode\", \"serial\"),\n"
    "            zone_delay_seconds=call.data.get(\"zone_delay_seconds\", 5),\n"
    "            enabled=call.data.get(\"enabled\", True),\n",
    "create schedule fields",
)

# Replace manual run start block with serial/parallel execution.
manual_pattern = r'''        # Start the first zone and pass the rest as queue\n.*?        # Trigger state update\n        await _trigger_state_update\(hass, entity_id\)'''
manual_replacement = '''        if schedule.execution_mode == "parallel":
            _LOGGER.info("Starting schedule %s in parallel mode", schedule_id)
            for zone_id, duration in queue:
                zone = system.zones.get(zone_id)
                if not zone:
                    _LOGGER.error("SCHEDULE ERROR: zone %d not found", zone_id)
                    continue
                if not system.start_zone(
                    zone_id, duration, schedule_id, allow_parallel=True
                ):
                    continue
                if zone.settings.switch_entity:
                    try:
                        await hass.services.async_call(
                            "switch",
                            "turn_on",
                            {"entity_id": zone.settings.switch_entity},
                            blocking=True,
                        )
                    except Exception as e:
                        _LOGGER.error(
                            "Failed to turn on switch for zone %d: %s", zone_id, e
                        )
        else:
            # Serial mode starts the first zone and passes the rest as a queue.
            first_zone_id, first_duration = queue[0]
            remaining_queue = queue[1:]
            zone = system.zones.get(first_zone_id)
            if not zone:
                _LOGGER.error(
                    "SCHEDULE ERROR: First zone %d not found", first_zone_id
                )
                return
            system.start_zone(first_zone_id, first_duration, schedule_id)
            zone.schedule_queue = remaining_queue
            if zone.settings.switch_entity:
                try:
                    await hass.services.async_call(
                        "switch",
                        "turn_on",
                        {"entity_id": zone.settings.switch_entity},
                        blocking=True,
                    )
                except Exception as e:
                    _LOGGER.error(
                        "Failed to turn on switch for zone %d: %s", first_zone_id, e
                    )

        # Trigger state update
        await _trigger_state_update(hass, entity_id)'''
text = replace_regex_once(text, manual_pattern, manual_replacement, "manual schedule execution")

# Pass the configured serial delay to continuation.
text = replace_once(
    text,
    "                        await self._start_next_scheduled_zone(\n"
    "                            schedule_queue, schedule_id\n"
    "                        )\n",
    "                        schedule = self.system.schedules.get(schedule_id)\n"
    "                        delay = schedule.zone_delay_seconds if schedule else 5\n"
    "                        await self._start_next_scheduled_zone(\n"
    "                            schedule_queue, schedule_id, delay\n"
    "                        )\n",
    "serial continuation delay",
)

# Replace automatic queue startup with shared serial/parallel logic.
auto_pattern = r'''                            if queue:\n                                # Start the first zone with queue\n.*?\n                            schedule\.last_run_date = now'''
auto_replacement = '''                            if queue:
                                if schedule.execution_mode == "parallel":
                                    for zone_id, duration in queue:
                                        zone_obj = self.system.zones.get(zone_id)
                                        if not zone_obj:
                                            continue
                                        if not self.system.start_zone(
                                            zone_id,
                                            duration,
                                            schedule.schedule_id,
                                            allow_parallel=True,
                                        ):
                                            continue
                                        switch_entity = zone_obj.settings.switch_entity
                                        if switch_entity:
                                            try:
                                                await self.hass.services.async_call(
                                                    "switch",
                                                    "turn_on",
                                                    {"entity_id": switch_entity},
                                                    blocking=True,
                                                )
                                            except Exception as e:
                                                _LOGGER.error(
                                                    "Failed to turn on %s: %s",
                                                    switch_entity,
                                                    e,
                                                )
                                else:
                                    first_zone_id, first_duration = queue[0]
                                    remaining_queue = queue[1:]
                                    zone_obj = self.system.zones.get(first_zone_id)
                                    if zone_obj:
                                        self.system.start_zone(
                                            first_zone_id,
                                            first_duration,
                                            schedule.schedule_id,
                                        )
                                        zone_obj.schedule_queue = remaining_queue
                                        switch_entity = zone_obj.settings.switch_entity
                                        if switch_entity:
                                            try:
                                                await self.hass.services.async_call(
                                                    "switch",
                                                    "turn_on",
                                                    {"entity_id": switch_entity},
                                                    blocking=True,
                                                )
                                            except Exception as e:
                                                _LOGGER.error(
                                                    "Failed to turn on %s: %s",
                                                    switch_entity,
                                                    e,
                                                )

                            schedule.last_run_date = now'''
text = replace_regex_once(text, auto_pattern, auto_replacement, "automatic schedule execution")

text = replace_once(
    text,
    "    async def _start_next_scheduled_zone(self, queue: list, schedule_id: str) -> None:\n",
    "    async def _start_next_scheduled_zone(\n"
    "        self, queue: list, schedule_id: str, delay_seconds: int = 5\n"
    "    ) -> None:\n",
    "continuation signature",
)
text = replace_once(
    text,
    "                await self._start_next_scheduled_zone(remaining_queue, schedule_id)\n",
    "                await self._start_next_scheduled_zone(\n"
    "                    remaining_queue, schedule_id, delay_seconds\n"
    "                )\n",
    "recursive continuation",
)
text = replace_once(
    text,
    "        # 5-second delay for valve protection between zones\n"
    "        _LOGGER.debug(\"    Waiting 5 seconds for valve protection...\")\n"
    "        await asyncio.sleep(5)\n",
    "        # User-configurable pause between serial zones.\n"
    "        if delay_seconds > 0:\n"
    "            _LOGGER.debug(\n"
    "                \"    Waiting %d seconds between serial zones...\",\n"
    "                delay_seconds,\n"
    "            )\n"
    "            await asyncio.sleep(delay_seconds)\n",
    "configured delay",
)
path.write_text(text)


# ---------------------------------------------------------------------------
# Sensor attributes exposed to the frontend
# ---------------------------------------------------------------------------
path = ROOT / "custom_components/smart_sprinkler_control/sensor.py"
text = path.read_text()
text = replace_once(
    text,
    "                \"zone_durations\": schedule.zone_durations,\n"
    "                \"zone_count\": len(schedule.zone_ids),\n",
    "                \"zone_durations\": schedule.zone_durations,\n"
    "                \"execution_mode\": schedule.execution_mode,\n"
    "                \"zone_delay_seconds\": schedule.zone_delay_seconds,\n"
    "                \"zone_count\": len(schedule.zone_ids),\n",
    "sensor schedule attributes",
)
path.write_text(text)


# ---------------------------------------------------------------------------
# Frontend schedule editor
# ---------------------------------------------------------------------------
path = ROOT / "frontend/src/schedules.js"
text = path.read_text()
text = replace_once(
    text,
    "      zone_durations: {},\n"
    "      enabled: true,\n",
    "      zone_durations: {},\n"
    "      execution_mode: 'serial',\n"
    "      zone_delay_seconds: 5,\n"
    "      enabled: true,\n",
    "frontend create defaults",
)
text = replace_once(
    text,
    "      zone_durations: {...(schedule.zone_durations || {})},\n"
    "      enabled: schedule.enabled !== false,\n",
    "      zone_durations: {...(schedule.zone_durations || {})},\n"
    "      execution_mode: schedule.execution_mode || 'serial',\n"
    "      zone_delay_seconds: Number(schedule.zone_delay_seconds ?? 5),\n"
    "      enabled: schedule.enabled !== false,\n",
    "frontend edit defaults",
)
text = replace_once(
    text,
    "        zone_durations: zoneDurations,\n"
    "        enabled: data.enabled,\n",
    "        zone_durations: zoneDurations,\n"
    "        execution_mode: data.execution_mode || 'serial',\n"
    "        zone_delay_seconds: Number(data.zone_delay_seconds ?? 5),\n"
    "        enabled: data.enabled,\n",
    "frontend save payload",
)
text = replace_once(
    text,
    "          const statusText = schedule.enabled ? 'Active' : 'Disabled';\n\n"
    "          return `\n",
    "          const statusText = schedule.enabled ? 'Active' : 'Disabled';\n"
    "          const mode = schedule.execution_mode || 'serial';\n"
    "          const modeText = mode === 'parallel' ? 'Parallel' : 'Serial';\n\n"
    "          return `\n",
    "frontend list mode variable",
)
text = replace_once(
    text,
    "              <span class=\"schedule-zones\">\n"
    "                <ha-icon icon=\"mdi:sprinkler-variant\"></ha-icon>\n"
    "                ${zoneCount} zone${zoneCount !== 1 ? 's' : ''}\n"
    "              </span>\n",
    "              <span class=\"schedule-zones\">\n"
    "                <ha-icon icon=\"mdi:sprinkler-variant\"></ha-icon>\n"
    "                ${zoneCount} zone${zoneCount !== 1 ? 's' : ''}\n"
    "              </span>\n"
    "              <span class=\"schedule-mode\">\n"
    "                <ha-icon icon=\"${mode === 'parallel' ? 'mdi:call-split' : 'mdi:format-list-numbered'}\"></ha-icon>\n"
    "                ${modeText}${mode === 'serial' ? ` · ${schedule.zone_delay_seconds ?? 5}s pause` : ''}\n"
    "              </span>\n",
    "frontend list mode display",
)
text = replace_once(
    text,
    "          <div class=\"form-group\">\n"
    "            <label>Select Zones</label>\n",
    "          <div class=\"form-group\">\n"
    "            <label>Execution Mode</label>\n"
    "            <select class=\"form-input\" value=\"${data.execution_mode || 'serial'}\"\n"
    "                    onchange=\"SmartSprinklerControlPanel.updateScheduleField('execution_mode', this.value); SmartSprinklerControlPanel.render()\">\n"
    "              <option value=\"serial\" ${(data.execution_mode || 'serial') === 'serial' ? 'selected' : ''}>Serial — zones run one after another</option>\n"
    "              <option value=\"parallel\" ${data.execution_mode === 'parallel' ? 'selected' : ''}>Parallel — all selected zones start together</option>\n"
    "            </select>\n"
    "          </div>\n"
    "          ${(data.execution_mode || 'serial') === 'serial' ? `\n"
    "          <div class=\"form-group\">\n"
    "            <label>Pause Between Zones (seconds)</label>\n"
    "            <input type=\"number\" class=\"form-input\" min=\"0\" max=\"3600\"\n"
    "                   value=\"${data.zone_delay_seconds ?? 5}\"\n"
    "                   onchange=\"SmartSprinklerControlPanel.updateScheduleField('zone_delay_seconds', Math.max(0, parseInt(this.value) || 0))\">\n"
    "          </div>\n"
    "          ` : ''}\n"
    "          <div class=\"form-group\">\n"
    "            <label>Select Zones</label>\n",
    "frontend execution controls",
)
text = replace_once(
    text,
    "            <label>Fire Order <span class=\"label-hint\">(drag to reorder)</span></label>\n",
    "            <label>${(data.execution_mode || 'serial') === 'serial' ? 'Zone Order' : 'Selected Zones'} "
    "<span class=\"label-hint\">${(data.execution_mode || 'serial') === 'serial' ? '(drag to reorder)' : '(start together)'}</span></label>\n",
    "frontend order label",
)
path.write_text(text)

print("Serial/parallel schedule changes applied successfully")
