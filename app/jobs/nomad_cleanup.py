import nomad
from app import Q
from app.utils.dns import discover_service
from datetime import timedelta, datetime
import os

from app.models import Box


@Q.job(func_or_queue="nomad", timeout=60000)
def cleanup_old_nomad_box(job_id):
    if os.getenv("FLASK_ENV") == "production":
        nomad_client = nomad.Nomad(discover_service("nomad").ip)
    else:
        nomad_client = nomad.Nomad(host=os.getenv("SEA_HOST", "0.0.0.0"))

    try:
        del_box_nomad(nomad_client, job_id)
    except nomad.api.exceptions.BaseNomadException:
        cleanup_old_nomad_box.schedule(timedelta(hours=2), job_id, timeout=60000)
        raise nomad.api.exceptions.BaseNomadException


@Q.job(func_or_queue="nomad", timeout=60000)
def expire_running_box(current_user, box):
    from app.services.box import BoxDeletionService
    BoxDeletionService(current_user=current_user, box=box).delete()


def del_box_nomad(nomad_client, job_id):
    nomad_client.job.deregister_job(job_id)


@Q.job(func_or_queue="nomad", timeout=100000)
def check_all_boxes():
    if os.getenv("FLASK_ENV") == "production":
        nomad_client = nomad.Nomad(discover_service("nomad").ip)
    else:
        nomad_client = nomad.Nomad(host=os.getenv("SEA_HOST", "0.0.0.0"))
    deployments = nomad_client.job.get_deployments("ssh-client")

    for deployment in deployments:
        box_exist = Box.query.filter_by(job_id=deployment).first()

        if datetime.utcnow >= box_exist.session_end_time:
            cleanup_old_nomad_box(deployment)
            continue

        if not box_exist:
            cleanup_old_nomad_box(deployment)
