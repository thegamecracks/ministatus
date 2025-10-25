from __future__ import annotations

from typing import TYPE_CHECKING, cast

import discord
from discord import Interaction

from ministatus.bot.errors import ErrorResponse

if TYPE_CHECKING:
    from ministatus.bot.bot import Bot


class LayoutView(discord.ui.LayoutView):
    async def on_error(
        self,
        interaction: Interaction,
        error: Exception,
        item: discord.ui.Item,
    ) -> None:
        if not isinstance(error, ErrorResponse):
            return await super().on_error(interaction, error, item)
        elif interaction.is_expired():
            return
        elif interaction.response.is_done():
            await interaction.followup.send(str(error), ephemeral=True)
        else:
            await interaction.response.send_message(str(error), ephemeral=True)


class CancellableView(LayoutView):
    _last_interaction: Interaction[Bot] | None = None

    async def interaction_check(self, interaction: Interaction) -> bool:
        if await super().interaction_check(interaction):
            self.set_last_interaction(interaction)
            return True
        return False

    async def on_timeout(self) -> None:
        if self._last_interaction is None:
            return
        elif self._last_interaction.is_expired():
            return
        elif not self._last_interaction.response.is_done():
            await self._last_interaction.response.defer()

        await self._last_interaction.delete_original_response()

    def set_last_interaction(self, interaction: Interaction) -> None:
        interaction = cast("Interaction[Bot]", interaction)
        self._last_interaction = interaction

    @property
    def last_interaction(self) -> Interaction[Bot]:
        if self._last_interaction is None:
            raise ValueError("Last interaction not set")
        return self._last_interaction


class Modal(discord.ui.Modal):
    async def on_error(self, interaction: Interaction, error: Exception) -> None:
        if not isinstance(error, ErrorResponse):
            return await super().on_error(interaction, error)
        elif interaction.is_expired():
            return
        elif interaction.response.is_done():
            await interaction.followup.send(str(error), ephemeral=True)
        else:
            await interaction.response.send_message(str(error), ephemeral=True)
