import os
import joblib
import skops.io as sio
from typing import Any

def save_model(model: Any, base_path: str) -> None:
    """Serializes the trained model using joblib and skops.
    
    Args:
        model: The trained model object.
        base_path: Base file path (without extension) where the model artifacts will be saved.
                   The function will append '.joblib' and '.skops' to save both formats.
    """
    # Ensure the directory exists
    dir_name = os.path.dirname(base_path)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)
        
    joblib_path = f"{base_path}.joblib"
    skops_path = f"{base_path}.skops"
    
    # Serialize with joblib
    joblib.dump(model, joblib_path)
    
    # Serialize securely with skops
    sio.dump(model, skops_path)
