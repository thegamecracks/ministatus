import datetime
import io
from typing import Sequence, cast

import discord
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import dates as mdates, ticker
from matplotlib.axes import Axes


def create_player_count_graph(
    datapoints: Sequence[tuple[datetime.datetime, int]],
    *,
    colour: int,
    max_players: int,
) -> io.BytesIO | None:
    def format_hour(x: float, pos: float) -> str:
        delta = cast(datetime.timedelta, mdates.num2timedelta(now_num - x))
        hours = round(abs(delta.total_seconds() / 3600))
        return f"{hours}h" if hours != 0 else "now"

    if len(datapoints) < 2:
        return

    assert 0 <= colour <= 0xFFFFFF
    colour_hex = f"#{colour:06X}"

    fig, ax = plt.subplots()

    # if any(None not in (d.min, d.max) for d in datapoints):
    #     # Resolution is not raw; generate bar graph with error bars
    #     pass

    # Plot player counts
    x = [p[0] for p in datapoints]
    y = [p[1] for p in datapoints]
    x_min, x_max = mdates.date2num(min(x)), mdates.date2num(max(x))
    ax.plot(x, y, colour_hex)  # , marker='.') # type: ignore

    # Set limits and fill under the line
    ax.set_xlim(x_min, x_max)  # type: ignore
    ax.set_ylim(0, max_players + 1)
    ax.fill_between(
        x,  # type: ignore
        y,  # type: ignore
        color=colour_hex + "55",
    )

    # Set xticks to every two hours
    now = discord.utils.utcnow()
    now_num = cast(float, mdates.date2num(now))
    step = 1 / 12
    start = x_max - step + (now_num - x_max)
    ax.set_xticks(np.arange(start, x_min, -step))
    ax.xaxis.set_major_formatter(format_hour)

    # Set yticks
    ax.yaxis.set_major_locator(ticker.MultipleLocator(5))

    # Add grid
    ax.set_axisbelow(True)
    ax.grid(color="#707070", alpha=0.4)

    # Color the ticks and make spine invisible
    for spine in ax.spines.values():
        spine.set_color("#00000000")
    ax.tick_params(labelsize=9, color="#70707066", labelcolor=colour_hex)

    set_axes_aspect(ax, 9 / 16, "box")

    f = io.BytesIO()
    fig.savefig(
        f,
        format="png",
        bbox_inches="tight",
        pad_inches=0.1,
        dpi=80,
        transparent=True,
    )
    # bbox_inches, pad_inches: removes padding around the graph
    f.seek(0)

    plt.close(fig)
    return f


def set_axes_aspect(ax: Axes, ratio: int | float, *args, **kwargs) -> None:
    """Set an Axes's aspect ratio.

    Extra arguments are passed through to `ax.set_aspect()`.

    :param ax: The Axes to set the aspect ratio for.
    :param ratio: The ratio of height to width.

    """
    # https://www.statology.org/matplotlib-aspect-ratio/
    x_left, x_right = ax.get_xlim()
    y_low, y_high = ax.get_ylim()
    x_size = x_right - x_left
    y_size = y_low - y_high
    current_ratio = abs(x_size / y_size)
    ax.set_aspect(current_ratio * ratio, *args, **kwargs)
