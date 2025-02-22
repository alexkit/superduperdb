import os
import random

import numpy as np
import pytest

try:
    import torch

    from superduperdb.ext.torch.model import TorchModel
    from superduperdb.ext.torch.tensor import tensor
except ImportError:
    torch = None

from superduperdb import CFG
from superduperdb.container.document import Document
from superduperdb.container.listener import Listener
from superduperdb.container.vector_index import VectorIndex
from superduperdb.db.mongodb.query import Collection
from superduperdb.server.dask_client import dask_client

'''
All pytest fixtures with _package scope_ are defined in this module.
Package scope means that the fixture will be executed once per package,
which in this case means once per `test/integration/` directory.

Fixtures included here can create:
- a MongoDB client
- a MongoDB collection with some basic data
- a local Dask client
- a local SuperDuperDB server linked to the MongoDB client

When adding new fixtures, please try to avoid building on top of other fixtures
as much as possible. This will make it easier to understand the test suite.
'''

# Set the seeds
random.seed(42)
torch and torch.manual_seed(42)
np.random.seed(42)


@pytest.fixture
def database_with_default_encoders_and_model(test_db):
    test_db.add(tensor(torch.float, shape=(32,)))
    test_db.add(tensor(torch.float, shape=(16,)))
    test_db.add(
        TorchModel(
            object=torch.nn.Linear(32, 16),
            identifier='model_linear_a',
            encoder='torch.float32[16]',
        )
    )
    test_db.add(
        Listener(
            select=Collection(name='documents').find(),
            key='x',
            model='model_linear_a',
        )
    )
    test_db.add(
        Listener(
            select=Collection(name='documents').find(),
            key='z',
            model='model_linear_a',
        )
    )
    vi = VectorIndex(
        identifier='test_index',
        indexing_listener='model_linear_a/x',
        compatible_listener='model_linear_a/z',
    )
    test_db.add(vi)
    yield test_db
    test_db.remove('model', 'model_linear_a', force=True)
    test_db.remove('encoder', 'torch.float32[16]', force=True)
    test_db.remove('encoder', 'torch.float32[32]', force=True)


@pytest.mark.skipif(not torch, reason='Torch not installed')
def fake_tensor_data(encoder, update: bool = True):
    data = []
    for i in range(10):
        x = torch.randn(32)
        y = int(random.random() > 0.5)
        z = torch.randn(32)
        data.append(
            Document(
                {
                    'x': encoder(x),
                    'y': y,
                    'z': encoder(z),
                    'update': update,
                }
            )
        )

    return data


@pytest.fixture
def fake_inserts(database_with_default_encoders_and_model):
    encoder = database_with_default_encoders_and_model.encoders['torch.float32[32]']
    return fake_tensor_data(encoder, update=False)


@pytest.fixture
def fake_updates(database_with_default_encoders_and_model):
    encoder = database_with_default_encoders_and_model.encoders['torch.float32[32]']
    return fake_tensor_data(encoder, update=True)


@pytest.fixture
def local_dask_client():
    os.environ[
        'SUPERDUPERDB_DATA_BACKEND'
    ] = 'mongodb://testmongodbuser:testmongodbpassword@localhost:27018/test_db'
    client = dask_client(CFG.cluster, local=True)
    yield client
    client.shutdown()
