"""
Compute Engine tools.

Provides instance management capabilities.
"""

import os

try:
    from google.cloud import compute_v1

    COMPUTE_AVAILABLE = True
except ImportError:
    COMPUTE_AVAILABLE = False


async def list_instances(zone: str | None = None) -> dict:
    """
    List Compute Engine instances.

    Args:
        zone: GCP zone (lists all zones if None)

    Returns:
        dict with list of instances
    """
    if not COMPUTE_AVAILABLE:
        return {
            "status": "error",
            "error": "google-cloud-compute not installed",
        }

    try:
        project_id = os.getenv("GCP_PROJECT_ID", "project38-483612")
        client = compute_v1.InstancesClient()

        instances = []

        if zone:
            # List instances in specific zone
            request = compute_v1.ListInstancesRequest(
                project=project_id,
                zone=zone,
            )
            for instance in client.list(request=request):
                instances.append(
                    {
                        "name": instance.name,
                        "zone": zone,
                        "status": instance.status,
                        "machine_type": instance.machine_type.split("/")[-1],
                    }
                )
        else:
            # List all zones and their instances
            zones_client = compute_v1.ZonesClient()
            zones_request = compute_v1.ListZonesRequest(project=project_id)

            for zone_obj in zones_client.list(request=zones_request):
                zone_name = zone_obj.name
                request = compute_v1.ListInstancesRequest(
                    project=project_id,
                    zone=zone_name,
                )
                for instance in client.list(request=request):
                    instances.append(
                        {
                            "name": instance.name,
                            "zone": zone_name,
                            "status": instance.status,
                            "machine_type": instance.machine_type.split("/")[-1],
                        }
                    )

        return {
            "status": "success",
            "count": len(instances),
            "instances": instances,
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
        }


async def get_instance_details(instance_name: str, zone: str) -> dict:
    """
    Get details of a specific instance.

    Args:
        instance_name: Name of the instance
        zone: GCP zone

    Returns:
        dict with instance details
    """
    if not COMPUTE_AVAILABLE:
        return {
            "status": "error",
            "error": "google-cloud-compute not installed",
        }

    try:
        project_id = os.getenv("GCP_PROJECT_ID", "project38-483612")
        client = compute_v1.InstancesClient()

        request = compute_v1.GetInstanceRequest(
            project=project_id,
            zone=zone,
            instance=instance_name,
        )

        instance = client.get(request=request)

        # Extract network interfaces
        network_interfaces = []
        for interface in instance.network_interfaces:
            network_interfaces.append(
                {
                    "network": interface.network.split("/")[-1],
                    "internal_ip": interface.network_i_p,
                    "external_ip": (
                        interface.access_configs[0].nat_i_p if interface.access_configs else None
                    ),
                }
            )

        return {
            "status": "success",
            "name": instance.name,
            "zone": zone,
            "instance_status": instance.status,
            "machine_type": instance.machine_type.split("/")[-1],
            "network_interfaces": network_interfaces,
            "created": str(instance.creation_timestamp),
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "instance_name": instance_name,
            "zone": zone,
        }


async def start_instance(instance_name: str, zone: str) -> dict:
    """
    Start a stopped instance.

    Args:
        instance_name: Name of the instance
        zone: GCP zone

    Returns:
        dict with operation status
    """
    if not COMPUTE_AVAILABLE:
        return {
            "status": "error",
            "error": "google-cloud-compute not installed",
        }

    try:
        project_id = os.getenv("GCP_PROJECT_ID", "project38-483612")
        client = compute_v1.InstancesClient()

        request = compute_v1.StartInstanceRequest(
            project=project_id,
            zone=zone,
            instance=instance_name,
        )

        operation = client.start(request=request)

        return {
            "status": "success",
            "instance_name": instance_name,
            "zone": zone,
            "operation_id": operation.name,
            "message": f"Instance {instance_name} start initiated",
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "instance_name": instance_name,
            "zone": zone,
        }


async def stop_instance(instance_name: str, zone: str) -> dict:
    """
    Stop a running instance.

    Args:
        instance_name: Name of the instance
        zone: GCP zone

    Returns:
        dict with operation status
    """
    if not COMPUTE_AVAILABLE:
        return {
            "status": "error",
            "error": "google-cloud-compute not installed",
        }

    try:
        project_id = os.getenv("GCP_PROJECT_ID", "project38-483612")
        client = compute_v1.InstancesClient()

        request = compute_v1.StopInstanceRequest(
            project=project_id,
            zone=zone,
            instance=instance_name,
        )

        operation = client.stop(request=request)

        return {
            "status": "success",
            "instance_name": instance_name,
            "zone": zone,
            "operation_id": operation.name,
            "message": f"Instance {instance_name} stop initiated",
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "instance_name": instance_name,
            "zone": zone,
        }
