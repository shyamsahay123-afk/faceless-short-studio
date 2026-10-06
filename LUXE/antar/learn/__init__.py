"""
ANTAR - the learn package.

`csv.parse(text)` reads one YouTube Studio CSV export;
`csv.all_metrics(config)` walks `output/analytics/`;
`csv.write_aggregate(config, metrics)` writes `aggregate.json`;
`recommend.learn(config)` ranks rotation values, writes `recommend.json`,
and closes the rotation-diff proof on the scorecard.
"""

from . import csv, recommend
from .csv import VideoMetric, parse
from .recommend import LearnError, learn, recommend_for_brief

__all__ = ["csv", "recommend", "VideoMetric", "parse", "LearnError",
           "learn", "recommend_for_brief"]
