class DataLoadError(Exception):
    """Error al cargar datos de origen."""
class ValidationError(Exception):
    """Datos que no cumplen reglas de negocio."""
class DataSaveError(Exception):
    """Error al guardar datos """