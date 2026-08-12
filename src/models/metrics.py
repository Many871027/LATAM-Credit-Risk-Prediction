import numpy as np
from sklearn.metrics import roc_auc_score, accuracy_score, log_loss

def calculate_roc_auc(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    """Calculates the Area Under the ROC Curve (ROC-AUC).
    
    Args:
        y_true: True binary labels (0 or 1).
        y_prob: Predicted default probabilities.
        
    Returns:
        float: ROC-AUC score.
    """
    return float(roc_auc_score(y_true, y_prob))

def calculate_gini(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    """Calculates the Gini index (2 * ROC-AUC - 1).
    
    Args:
        y_true: True binary labels (0 or 1).
        y_prob: Predicted default probabilities.
        
    Returns:
        float: Gini index.
    """
    roc_auc = calculate_roc_auc(y_true, y_prob)
    return 2.0 * roc_auc - 1.0

def calculate_ks(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    """Calculates the Kolmogorov-Smirnov (KS) statistic.
    
    The KS statistic is the maximum separation between the cumulative distribution
    functions of default (class 1) and non-default (class 0) groups.
    
    Args:
        y_true: True binary labels (0 or 1).
        y_prob: Predicted default probabilities.
        
    Returns:
        float: KS statistic (as a fraction between 0.0 and 1.0).
    """
    y_true = np.asarray(y_true)
    y_prob = np.asarray(y_prob)
    
    probs_default = y_prob[y_true == 1]
    probs_non_default = y_prob[y_true == 0]
    
    if len(probs_default) == 0 or len(probs_non_default) == 0:
        return 0.0
        
    thresholds = np.sort(np.unique(y_prob))
    
    # ECDF using searchsorted
    cdf_default = np.searchsorted(np.sort(probs_default), thresholds, side='right') / len(probs_default)
    cdf_non_default = np.searchsorted(np.sort(probs_non_default), thresholds, side='right') / len(probs_non_default)
    
    ks_stat = np.max(np.abs(cdf_non_default - cdf_default))
    return float(ks_stat)

def calculate_accuracy(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Calculates classification accuracy."""
    return float(accuracy_score(y_true, y_pred))

def calculate_log_loss(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    """Calculates binary cross-entropy (log loss)."""
    return float(log_loss(y_true, y_prob))
