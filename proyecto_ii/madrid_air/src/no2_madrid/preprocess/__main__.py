"""Limpieza de las fuentes municipales usando la configuración central."""
from no2_madrid.config import Settings
from no2_madrid.pipeline import preprocess


def main():
    preprocess(Settings.from_env())


if __name__ == "__main__":
    main()
