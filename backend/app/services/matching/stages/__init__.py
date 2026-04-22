"""Pipeline stage implementations.

Each stage is a small class exposing ``name`` and ``run(state)``. See
``base.py`` for the protocol. Stages are composed by ``run_pipeline``
in ``matching/pipeline.py``.
"""
