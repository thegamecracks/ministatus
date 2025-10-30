import datetime
import io
import math
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
) -> io.BytesIO:
    now = discord.utils.utcnow()
    if len(datapoints) < 2:
        datapoints = [
            (now - datetime.timedelta(minutes=1), 0),
            (now, 0),
        ]

    assert 0 <= colour <= 0xFFFFFF
    colour_hex = f"#{colour:06X}"

    fig, ax = plt.subplots()

    # Plot player counts
    x = [p[0] for p in datapoints]
    y = [p[1] for p in datapoints]
    x_min = cast(float, mdates.date2num(min(x)))
    x_max = cast(float, mdates.date2num(max(x)))
    ax.plot(x, y, colour_hex)  # , marker='.') # type: ignore

    # Set limits and fill under the line
    ax.set_xlim(x_min, x_max)  # type: ignore
    ax.set_ylim(0, max(max_players, max(y), 1))
    ax.fill_between(
        x,  # type: ignore
        y,  # type: ignore
        color=colour_hex + "55",
    )

    now_num = cast(float, mdates.date2num(now))
    _set_relative_date_xticks(ax, now_num, x_min, x_max)

    # Set yticks
    y_step = math.ceil(max_players / 10) or 5
    ax.yaxis.set_major_locator(ticker.MultipleLocator(y_step))

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


def _set_relative_date_xticks(ax: Axes, now: float, x_min: float, x_max: float) -> None:
    def format_hour(x: float, pos: float) -> str:
        # Generate ticks based exactly on the tick position and step.
        # Floating point errors can still occur from this, so unfortunately
        # we have to round anyway.

        pos += 1  # bump 0-indexed to 1-indexed for our math

        if step >= 1:
            days = round(pos * step)
            return f"{days}d"
        elif step >= 1 / 24:
            hours = round(pos * step * 24)
            return f"{hours}h"
        elif step >= 1 / 24 / 60:
            minutes = round(pos * step * 24 * 60)
            return f"{minutes}m"

        seconds = round(pos * step * 24 * 60 * 60)
        return f"{seconds}s"

    step = _calculate_date_step(x_min, x_max)
    start = x_max - step + (now - x_max)
    ax.set_xticks(np.arange(start, x_min, -step))
    ax.xaxis.set_major_formatter(format_hour)


def _calculate_date_step(x_min: float, x_max: float) -> float:
    # Figure out a reasonable interval to use for x-ticks.
    # Remember that date2num() = 1 day, so 1 / 24 is 1 hour.
    span_days = x_max - x_min
    max_ticks = 16
    possible_steps = [1 / 24 / 4, 1 / 24, 1 / 12, 1 / 6, 1 / 3, 1, 3, 30]

    for pstep in possible_steps:
        if span_days / pstep <= max_ticks:
            return pstep

    return possible_steps[-1]


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
