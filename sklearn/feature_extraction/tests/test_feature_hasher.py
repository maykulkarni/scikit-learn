from __future__ import unicode_literals

import numpy as np
import pytest
from numpy.testing import assert_array_equal

from sklearn.feature_extraction import FeatureHasher
from sklearn.utils.testing import (assert_raises, assert_true, assert_equal,
                                   ignore_warnings, assert_raise_message)


def test_feature_hasher_dicts():
    h = FeatureHasher(n_features=16)
    assert_equal("dict", h.input_type)

    raw_X = [{"foo": "bar", "dada": 42, "tzara": 37},
             {"foo": "baz", "gaga": u"string1"}]
    X1 = FeatureHasher(n_features=16).transform(raw_X)
    gen = (iter(d.items()) for d in raw_X)
    X2 = FeatureHasher(n_features=16, input_type="pair").transform(gen)
    assert_array_equal(X1.toarray(), X2.toarray())


@ignore_warnings(category=DeprecationWarning)
def test_feature_hasher_strings():
    # mix byte and Unicode strings; note that "foo" is a duplicate in row 0
    raw_X = [["foo", "bar", "baz", "foo".encode("ascii")],
             ["bar".encode("ascii"), "baz", "quux"]]

    for lg_n_features in (7, 9, 11, 16, 22):
        n_features = 2 ** lg_n_features

        it = (x for x in raw_X)                 # iterable

        h = FeatureHasher(n_features, non_negative=True, input_type="string")
        X = h.transform(it)

        assert_equal(X.shape[0], len(raw_X))
        assert_equal(X.shape[1], n_features)

        assert_true(np.all(X.data > 0))
        assert_equal(X[0].sum(), 4)
        assert_equal(X[1].sum(), 3)

        assert_equal(X.nnz, 6)


def test_feature_hasher_pairs():
    raw_X = (iter(d.items()) for d in [{"foo": 1, "bar": 2},
                                       {"baz": 3, "quux": 4, "foo": -1}])
    h = FeatureHasher(n_features=16, input_type="pair")
    x1, x2 = h.transform(raw_X).toarray()
    x1_nz = sorted(np.abs(x1[x1 != 0]))
    x2_nz = sorted(np.abs(x2[x2 != 0]))
    assert_equal([1, 2], x1_nz)
    assert_equal([1, 3, 4], x2_nz)


def test_feature_hasher_pairs_with_string_values():
    raw_X = (iter(d.items()) for d in [{"foo": 1, "bar": "a"},
                                       {"baz": u"abc", "quux": 4, "foo": -1}])
    h = FeatureHasher(n_features=16, input_type="pair")
    x1, x2 = h.transform(raw_X).toarray()
    x1_nz = sorted(np.abs(x1[x1 != 0]))
    x2_nz = sorted(np.abs(x2[x2 != 0]))
    assert_equal([1, 1], x1_nz)
    assert_equal([1, 1, 4], x2_nz)

    raw_X = (iter(d.items()) for d in [{"bax": "abc"},
                                       {"bax": "abc"}])
    x1, x2 = h.transform(raw_X).toarray()
    x1_nz = np.abs(x1[x1 != 0])
    x2_nz = np.abs(x2[x2 != 0])
    assert_equal([1], x1_nz)
    assert_equal([1], x2_nz)
    assert_array_equal(x1, x2)


def test_hash_empty_input():
    n_features = 16
    raw_X = [[], (), iter(range(0))]

    h = FeatureHasher(n_features=n_features, input_type="string")
    X = h.transform(raw_X)

    assert_array_equal(X.A, np.zeros((len(raw_X), n_features)))


def test_hasher_invalid_input():
    assert_raises(ValueError, FeatureHasher, input_type="gobbledygook")
    assert_raises(ValueError, FeatureHasher, n_features=-1)
    assert_raises(ValueError, FeatureHasher, n_features=0)
    assert_raises(TypeError, FeatureHasher, n_features='ham')

    h = FeatureHasher(n_features=np.uint16(2 ** 6))
    assert_raises(ValueError, h.transform, [])
    assert_raises(Exception, h.transform, [[5.5]])
    assert_raises(Exception, h.transform, [[None]])


def test_hasher_set_params():
    # Test delayed input validation in fit (useful for grid search).
    hasher = FeatureHasher()
    hasher.set_params(n_features=np.inf)
    assert_raises(TypeError, hasher.fit)


def test_hasher_zeros():
    # Assert that no zeros are materialized in the output.
    X = FeatureHasher().transform([{'foo': 0}])
    assert_equal(X.data.shape, (0,))


@ignore_warnings(category=DeprecationWarning)
def test_hasher_alternate_sign():
    X = [list("Thequickbrownfoxjumped")]

    Xt = FeatureHasher(alternate_sign=True, non_negative=False,
                       input_type='string').fit_transform(X)
    assert Xt.data.min() < 0 and Xt.data.max() > 0

    Xt = FeatureHasher(alternate_sign=True, non_negative=True,
                       input_type='string').fit_transform(X)
    assert Xt.data.min() > 0

    Xt = FeatureHasher(alternate_sign=False, non_negative=True,
                       input_type='string').fit_transform(X)
    assert Xt.data.min() > 0
    Xt_2 = FeatureHasher(alternate_sign=False, non_negative=False,
                         input_type='string').fit_transform(X)
    # With initially positive features, the non_negative option should
    # have no impact when alternate_sign=False
    assert_array_equal(Xt.data, Xt_2.data)


@ignore_warnings(category=DeprecationWarning)
def test_hash_collisions():
    X = [list("Thequickbrownfoxjumped")]

    Xt = FeatureHasher(alternate_sign=True, non_negative=False,
                       n_features=1, input_type='string').fit_transform(X)
    # check that some of the hashed tokens are added
    # with an opposite sign and cancel out
    assert abs(Xt.data[0]) < len(X[0])

    Xt = FeatureHasher(alternate_sign=True, non_negative=True,
                       n_features=1, input_type='string').fit_transform(X)
    assert abs(Xt.data[0]) < len(X[0])

    Xt = FeatureHasher(alternate_sign=False, non_negative=True,
                       n_features=1, input_type='string').fit_transform(X)
    assert Xt.data[0] == len(X[0])


@ignore_warnings(category=DeprecationWarning)
def test_hasher_negative():
    X = [{"foo": 2, "bar": -4, "baz": -1}.items()]
    Xt = FeatureHasher(alternate_sign=False, non_negative=False,
                       input_type="pair").fit_transform(X)
    assert_true(Xt.data.min() < 0 and Xt.data.max() > 0)
    Xt = FeatureHasher(alternate_sign=False, non_negative=True,
                       input_type="pair").fit_transform(X)
    assert_true(Xt.data.min() > 0)
    Xt = FeatureHasher(alternate_sign=True, non_negative=False,
                       input_type="pair").fit_transform(X)
    assert_true(Xt.data.min() < 0 and Xt.data.max() > 0)
    Xt = FeatureHasher(alternate_sign=True, non_negative=True,
                       input_type="pair").fit_transform(X)
    assert_true(Xt.data.min() > 0)


@pytest.mark.parametrize("X, expected_output, input_type", [
    ([{'dog': 1, 'cat': 3}, {'elephant': 9, 'bird': 32}],
        [[], [], ['elephant'], ['dog'], ['cat', 'bird']],
        'dict'),

    (["a", "b", "c", "x", "y", "z"],
        [['a', 'z'], ['b'], ['c'], ['x'], ['y']],
        'string')
])
def test_hasher_order(X, expected_output, input_type):
    hasher = FeatureHasher(n_features=5, save_mappings="fit",
                           input_type=input_type)
    hasher.fit_transform(X)
    actual = hasher.get_feature_names()
    # orderings in the list are not always the same, hence
    # create a set for matching ['x', 'y'] with ['y', 'x']
    assert all(set(x) == set(y) for x, y in zip(expected_output, actual))


def test_hasher_get_feature_without_transform():
    hasher = FeatureHasher(n_features=5, save_mappings="fit")
    exception_message = ("FeatureHasher has not transformed yet. Please"
                         " call .fit_transform() first.")
    assert_raises(ValueError, hasher.get_feature_names)
    assert_raise_message(ValueError, exception_message,
                         hasher.get_feature_names)


def test_hasher_get_feature_without_save_mappings():
    X = ["uzumaki", "naruto", "dattebayoo"]
    hasher = FeatureHasher(n_features=2, input_type='string')
    hasher.fit_transform(X)
    exception_message = ("FeatureHasher was instantiated with"
                         " save_mappings=False (default) Please pass in"
                         " save_mappings=True to save the mappings.")
    assert_raises(ValueError, hasher.get_feature_names)
    assert_raise_message(ValueError, exception_message,
                         hasher.get_feature_names)


def test_hasher_get_feature_fit():
    X = ["a", "b", "c"]
    X2 = ["d", "e", "f"]
    expected_feature_names = [['a'], ['b'], ['c'], [], []]
    hasher = FeatureHasher(n_features=5, input_type="string",
                           save_mappings="fit")
    hasher.fit_transform(X)
    assert hasher.get_feature_names() == expected_feature_names
    hasher.transform(X2)
    assert hasher.get_feature_names() == expected_feature_names


def test_hasher_get_feature_both():
    X = ["a", "b", "c"]
    X2 = ["d", "e", "f"]
    expected_feature_names_X = [['a'], ['b'], ['c'], [], []]
    expected_feature_names_X2 = [[], [], [], ['f'], ['e', 'd']]
    hasher = FeatureHasher(n_features=5, input_type="string",
                           save_mappings="always")
    hasher.fit_transform(X)
    actual_X = hasher.get_feature_names()
    hasher.transform(X2)
    actual_X2 = hasher.get_feature_names()
    # orderings in the list are not always the same, hence
    # create a set for matching ['x', 'y'] with ['y', 'x']
    assert all(set(x) == set(y) for x, y in zip(expected_feature_names_X,
                                                actual_X))
    assert all(set(x) == set(y) for x, y in zip(expected_feature_names_X2,
                                                actual_X2))


def test_feature_hasher_save_mappings_arg():
    def make_hasher():
        hasher = FeatureHasher(n_features=5, input_type="string",
                               save_mappings="naruto")
        hasher.fit_transform(["a"])
    msg = ("Unknown parameter passed to save_mappings: '{0}'"
           ". Valid parameters are 'fit', 'always' or False"
           .format("naruto"))
    assert_raise_message(ValueError, msg, make_hasher)
