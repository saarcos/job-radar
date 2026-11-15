from jobradar.adapters.sources.getonboard import GetOnBoardSource
from jobradar.adapters.sources.weworkremotely import WeWorkRemotelySource
from jobradar.ports.job_source import JobSource

# Every source the sync runs. Typed with the port, so mypy checks that each
# adapter has what JobSource asks for: a missing or mistyped method fails the
# type check here, not the first sync.
SOURCES: tuple[JobSource, ...] = (GetOnBoardSource(), WeWorkRemotelySource())
