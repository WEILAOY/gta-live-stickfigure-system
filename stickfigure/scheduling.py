"""Timestamp cadence without rounding every interval up to a source-frame gap."""
import math

def analysis_max_age(rate,total_ms,completions=()):
    """Bounded freshness budget based on measured latency and result cadence.

    Does not preserve targets missing from a newer completed result.
    """
    interval=1/max(1,float(rate));latency=max(0,float(total_ms))/1000
    recent=completions[-7:]
    gap=max((b-a for a,b in zip(recent,recent[1:])),default=0)
    return min(1.5,max(.35,2*interval+.08,latency+max(interval,latency*.75)+.15,gap+latency+.15))


class FrameCadence:
    def __init__(self):
        self.reset()

    def reset(self):
        self.next_due=None
        self.previous=None
        self.rate=None

    def ready(self,timestamp,rate):
        if rate<=0:
            return False
        if self.rate!=rate or (self.previous is not None and timestamp<self.previous-.02):
            self.reset()
        self.rate=rate
        self.previous=timestamp
        interval=1/rate
        if self.next_due is None:
            self.next_due=timestamp+interval
            return True
        if timestamp+1e-6<self.next_due:
            return False
        self.next_due+=max(1,math.floor((timestamp-self.next_due+1e-6)/interval)+1)*interval
        return True
