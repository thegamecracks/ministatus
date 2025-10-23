import discord


class PlaceholderView(discord.ui.LayoutView):
    container = discord.ui.Container()

    def __init__(self, user: discord.Member | discord.User) -> None:
        super().__init__()
        self.container.add_item(discord.ui.TextDisplay("## Mini Status"))
        self.container.add_item(discord.ui.Separator())
        self.container.add_item(
            discord.ui.TextDisplay(
                f"Hey there! I'm a placeholder message sent by {user.mention}.\n"
                f"This message isn't doing anything, for now..."
            )
        )
