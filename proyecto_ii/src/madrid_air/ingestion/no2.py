from madrid_air.ingestion.common import municipal_files


def fetch(client, settings):
    return municipal_files(client, settings, "201200-0-calidad-aire-horario", "no2")
