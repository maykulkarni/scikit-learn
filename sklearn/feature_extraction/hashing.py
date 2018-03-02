# Author: Lars Buitinck
# License: BSD 3 clause

import numbers
import warnings

import numpy as np
import scipy.sparse as sp
from sklearn.utils.validation import check_is_fitted

from . import _hashing
from ..base import BaseEstimator, TransformerMixin


def _iteritems(d):
    """Like d.iteritems, but accepts any collections.Mapping."""
    return d.iteritems() if hasattr(d, "iteritems") else d.items()


class FeatureHasher(BaseEstimator, TransformerMixin):
    """Implements feature hashing, aka the hashing trick.

    This class turns sequences of symbolic feature names (strings) into
    scipy.sparse matrices, using a hash function to compute the matrix column
    corresponding to a name. The hash function employed is the signed 32-bit
    version of Murmurhash3.

    Feature names of type byte string are used as-is. Unicode strings are
    converted to UTF-8 first, but no Unicode normalization is done.
    Feature values must be (finite) numbers.

    This class is a low-memory alternative to DictVectorizer and
    CountVectorizer, intended for large-scale (online) learning and situations
    where memory is tight, e.g. when running prediction code on embedded
    devices.

    Read more in the :ref:`User Guide <feature_hashing>`.

    Parameters
    ----------
    n_features : integer, optional
        The number of features (columns) in the output matrices. Small numbers
        of features are likely to cause hash collisions, but large numbers
        will cause larger coefficient dimensions in linear learners.
    input_type : string, optional, default "dict"
        Either "dict" (the default) to accept dictionaries over
        (feature_name, value); "pair" to accept pairs of (feature_name, value);
        or "string" to accept single strings.
        feature_name should be a string, while value should be a number.
        In the case of "string", a value of 1 is implied.
        The feature_name is hashed to find the appropriate column for the
        feature. The value's sign might be flipped in the output (but see
        non_negative, below).
    dtype : numpy type, optional, default np.float64
        The type of feature values. Passed to scipy.sparse matrix constructors
        as the dtype argument. Do not set this to bool, np.boolean or any
        unsigned integer type.
    alternate_sign : boolean, optional, default True
        When True, an alternating sign is added to the features as to
        approximately conserve the inner product in the hashed space even for
        small n_features. This approach is similar to sparse random projection.
    non_negative : boolean, optional, default False
        When True, an absolute value is applied to the features matrix prior to
        returning it. When used in conjunction with alternate_sign=True, this
        significantly reduces the inner product preservation property.

        .. deprecated:: 0.19
            This option will be removed in 0.21.
    save_mappings : {"fit", "always"}, default False
        Possible values are : "fit" or "always". When "fit", FeatureHasher will
        save the mappings between feature seen in training data, and the
        corresponding column only once during fit time. When "always", mappings
        will be continued to be stored even during the subsequent transform
        calls. By default, no mappings will be stored for performance reasons.


    Examples
    --------
    >>> from sklearn.feature_extraction import FeatureHasher
    >>> h = FeatureHasher(n_features=10)
    >>> D = [{'dog': 1, 'cat':2, 'elephant':4},{'dog': 2, 'run': 5}]
    >>> f = h.transform(D)
    >>> f.toarray()
    array([[ 0.,  0., -4., -1.,  0.,  0.,  0.,  0.,  0.,  2.],
           [ 0.,  0.,  0., -2., -5.,  0.,  0.,  0.,  0.,  0.]])

    See also
    --------
    DictVectorizer : vectorizes string-valued features using a hash table.
    sklearn.preprocessing.OneHotEncoder : handles nominal/categorical features
        encoded as columns of integers.
    """

    def __init__(self, n_features=(2 ** 20), input_type="dict",
                 dtype=np.float64, alternate_sign=True, non_negative=False,
                 save_mappings=False):
        self._validate_params(n_features, input_type, save_mappings)
        if non_negative:
            warnings.warn("the option non_negative=True has been deprecated"
                          " in 0.19 and will be removed"
                          " in version 0.21.", DeprecationWarning)

        self.dtype = dtype
        self.input_type = input_type
        self.n_features = n_features
        self.alternate_sign = alternate_sign
        self.non_negative = non_negative
        self.save_mappings = save_mappings

    @staticmethod
    def _validate_params(n_features, input_type, save_mappings):
        # strangely, np.int16 instances are not instances of Integral,
        # while np.int64 instances are...
        if not isinstance(n_features, (numbers.Integral, np.integer)):
            raise TypeError("n_features must be integral, got %r (%s)."
                            % (n_features, type(n_features)))
        elif n_features < 1 or n_features >= 2 ** 31:
            raise ValueError("Invalid number of features (%d)." % n_features)

        if input_type not in ("dict", "pair", "string"):
            raise ValueError("input_type must be 'dict', 'pair' or 'string',"
                             " got %r." % input_type)
        if save_mappings not in (False, "always", "fit"):
            raise ValueError("Unknown parameter passed to save_mappings: '{0}'"
                             ". Valid parameters are 'fit', 'always' or False"
                             .format(save_mappings))

    def _transform(self, raw_X, save_mappings):
        raw_X = iter(raw_X)
        if self.input_type == "dict":
            raw_X = (_iteritems(d) for d in raw_X)
        elif self.input_type == "string":
            raw_X = (((f, 1) for f in x) for x in raw_X)

        indices, indptr, values, feature_to_index_map_ = \
            _hashing.transform(raw_X, self.n_features, self.dtype,
                               self.alternate_sign, save_mappings)

        if save_mappings:
            self.feature_to_index_map_ = feature_to_index_map_

        n_samples = indptr.shape[0] - 1
        if n_samples == 0:
            raise ValueError("Cannot vectorize empty sequence.")

        X = sp.csr_matrix((values, indices, indptr), dtype=self.dtype,
                          shape=(n_samples, self.n_features))
        X.sum_duplicates()  # also sorts the indices

        if self.non_negative:
            np.abs(X.data, X.data)
        return X

    def fit_transform(self, X, y=None, **fit_params):
        """This method fits the values when save_mappings is set to true.
        Otherwise, the values are learnt at transform time.

        Parameters
        ----------
        X : iterable over iterable over raw features, length = n_samples
            Samples. Each sample must be iterable an (e.g., a list or tuple)
            containing/generating feature names (and optionally values, see
            the input_type constructor argument) which will be hashed.
            raw_X need not support the len function, so it can be the result
            of a generator; n_samples is determined on the fly.

        y : this parameter is ignored.

        fit_params : this parameter is ignored.

        Returns
        -------
        X : scipy.sparse matrix, shape = (n_samples, self.n_features)
            Feature matrix, for use with estimators or further transformers"""

        return self._transform(X, self.save_mappings is not None)

    def fit(self, X=None, y=None):
        """This method calls fit_transform if save_mappings is not None.
        Otherwise, it doesn't do anything.

        Parameters
        ----------
        X : array-like

        Returns
        -------
        self : FeatureHasher

        """
        # repeat input validation for grid search (which calls set_params)
        self._validate_params(self.n_features, self.input_type,
                              self.save_mappings)
        if self.save_mappings:
            self.fit_transform(X)
        return self

    def transform(self, raw_X):
        """Transform a sequence of instances to a scipy.sparse matrix.

        Parameters
        ----------
        raw_X : iterable over iterable over raw features, length = n_samples
            Samples. Each sample must be iterable an (e.g., a list or tuple)
            containing/generating feature names (and optionally values, see
            the input_type constructor argument) which will be hashed.
            raw_X need not support the len function, so it can be the result
            of a generator; n_samples is determined on the fly.

        Returns
        -------
        X : scipy.sparse matrix, shape = (n_samples, self.n_features)
            Feature matrix, for use with estimators or further transformers.

        """
        if self.save_mappings == "always":
            return self._transform(raw_X, save_mappings=True)
        else:
            return self._transform(raw_X, save_mappings=False)

    def get_feature_names(self):
        """Returns a list of the feature mappings.

        Returns
        -------
        feature_names : list of the feature mappings. For features that were
            not active in training are denoted by empty lists. Those that
            contain multiple n_grams are contained within a single list.
        """
        if not self.save_mappings:
            raise ValueError("FeatureHasher was instantiated with"
                             " save_mappings=False (default) Please pass in"
                             " save_mappings=True to save the mappings.")
        check_is_fitted(self, "feature_to_index_map_",
                        "FeatureHasher has not transformed yet. Please"
                        " call .fit_transform() first.")
        reversed_dict = self._reverse_dict(self.feature_to_index_map_)
        # return the results as a list for consistency with
        # DictVectorizer.get_feature_names
        feature_names = [reversed_dict.setdefault(i, [])
                         for i in range(self.n_features)]
        return feature_names

    @staticmethod
    def _reverse_dict(old_dict):
        new_dict = {}
        for key, value in old_dict.items():
            # keys are received as bytes on Python 3, hence the decode
            new_dict.setdefault(value, []).append(key.decode("utf-8"))
        return new_dict
