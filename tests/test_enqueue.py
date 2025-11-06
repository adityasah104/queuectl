import os
import tempfile
from queuectl.core.storage import Storage
from queuectl.core.job import Job

def test_add_and_get_job(tmp_path):
    # Create a temporary DB file in pytest temp directory
    db_file = tmp_path / "test_queuectl.db"

    # Patch Storage to use this DB file
    from queuectl.core import storage
    storage.DB_FILE = str(db_file)

    s = Storage()
    job = Job.from_dict({"command": "echo test"}) # auto-generate ID
    s.add_job(job)

    j = s.get_job(job.id)
    assert j["id"] == job.id
    assert j["command"] == "echo test"
