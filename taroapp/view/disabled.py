from taroapp import printer
from taroapp.printer import Column

JOB_ID = Column('DISABLED JOB ID', 30, lambda dj: dj.job_id, lambda _: "")
REGEX = Column('REGEX', 30, lambda dj: 'yes' if dj.regex else 'no', lambda _: "")
DISABLED = Column('DISABLED', 30, lambda dj: printer.format_dt(dj.created), lambda _: "")

DEFAULT_COLUMNS = [JOB_ID, REGEX, DISABLED]
