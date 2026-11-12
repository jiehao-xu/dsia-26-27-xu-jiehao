from madrid_air.ingestion.common import download, resources


def fetch(client, settings):
    resource = next(r for r in resources(client, "300082-0-calendario_laboral")
                    if r.get("format", "").upper() == "CSV")
    yield download(client, resource["url"], settings.root / "data/raw/calendar",
                   resource["id"], ".csv", refresh=True)
