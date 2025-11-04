"""
Checkpoint Manager for Patient Timeline Abstraction

Provides phase-level checkpointing to enable restart from any phase
in case of failure or interruption.

Author: Claude
Date: 2025-11-03
Version: 1.0
"""

import json
import pickle
import os
from typing import Dict, Any, Optional
from datetime import datetime
from dataclasses import asdict, is_dataclass
from pathlib import Path


class DataclassJSONEncoder(json.JSONEncoder):
    """
    Custom JSON encoder that handles dataclasses and other non-serializable objects.

    This encoder safely converts:
    - Dataclasses → dicts (via asdict())
    - FeatureObject/SourceRecord/Adjudication → dicts
    - Other objects → string representation
    """
    def default(self, obj):
        # Handle dataclasses (SourceRecord, Adjudication, etc.)
        if is_dataclass(obj):
            return asdict(obj)

        # Handle objects with to_dict() method (FeatureObject)
        if hasattr(obj, 'to_dict') and callable(obj.to_dict):
            return obj.to_dict()

        # Fallback to string representation
        try:
            return str(obj)
        except:
            return f"<non-serializable: {type(obj).__name__}>"


class CheckpointManager:
    """
    Manages phase-level checkpoints for the timeline abstraction workflow.

    Checkpoints are saved after each phase completes, allowing restart
    from any phase in case of failure.
    """

    CHECKPOINT_VERSION = "1.0"

    def __init__(self, patient_id: str, output_dir: str):
        """
        Initialize checkpoint manager.

        Args:
            patient_id: Patient FHIR ID
            output_dir: Output directory for checkpoints
        """
        self.patient_id = patient_id
        self.checkpoint_dir = Path(output_dir) / "checkpoints"
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

        # Checkpoint metadata
        self.metadata = {
            'version': self.CHECKPOINT_VERSION,
            'patient_id': patient_id,
            'phases_completed': [],
            'last_checkpoint': None,
            'started_at': datetime.utcnow().isoformat() + 'Z'
        }

    def save_checkpoint(self, phase_name: str, state: Dict[str, Any]) -> str:
        """
        Save a checkpoint for the given phase.

        Args:
            phase_name: Name of the phase (e.g., "phase_1_data_loading")
            state: Dictionary containing all state to checkpoint

        Returns:
            Path to the saved checkpoint file
        """
        checkpoint_file = self.checkpoint_dir / f"{phase_name}.json"

        # Update metadata
        self.metadata['phases_completed'].append(phase_name)
        self.metadata['last_checkpoint'] = phase_name
        self.metadata['last_checkpoint_time'] = datetime.utcnow().isoformat() + 'Z'

        # Prepare checkpoint data
        checkpoint_data = {
            'metadata': self.metadata.copy(),
            'phase': phase_name,
            'state': state,
            'saved_at': datetime.utcnow().isoformat() + 'Z'
        }

        # Save checkpoint using custom JSON encoder
        with open(checkpoint_file, 'w') as f:
            json.dump(checkpoint_data, f, indent=2, cls=DataclassJSONEncoder)

        # Also save metadata file
        metadata_file = self.checkpoint_dir / "metadata.json"
        with open(metadata_file, 'w') as f:
            json.dump(self.metadata, f, indent=2)

        print(f"✅ Checkpoint saved: {checkpoint_file.name} ({checkpoint_file.stat().st_size / 1024:.1f} KB)")
        return str(checkpoint_file)

    def load_checkpoint(self, phase_name: str) -> Optional[Dict[str, Any]]:
        """
        Load a checkpoint for the given phase.

        Args:
            phase_name: Name of the phase to load

        Returns:
            Dictionary containing checkpoint state, or None if not found
        """
        checkpoint_file = self.checkpoint_dir / f"{phase_name}.json"

        if not checkpoint_file.exists():
            return None

        with open(checkpoint_file, 'r') as f:
            checkpoint_data = json.load(f)

        print(f"✅ Checkpoint loaded: {checkpoint_file.name} (saved at {checkpoint_data['saved_at']})")
        return checkpoint_data['state']

    def get_latest_checkpoint(self) -> Optional[str]:
        """
        Get the name of the latest successfully completed phase.

        Returns:
            Phase name of the latest checkpoint, or None if no checkpoints exist
        """
        metadata_file = self.checkpoint_dir / "metadata.json"

        if not metadata_file.exists():
            return None

        with open(metadata_file, 'r') as f:
            metadata = json.load(f)

        return metadata.get('last_checkpoint')

    def list_checkpoints(self) -> list:
        """
        List all available checkpoints.

        Returns:
            List of phase names with available checkpoints
        """
        if not self.checkpoint_dir.exists():
            return []

        checkpoints = []
        for file in self.checkpoint_dir.glob("phase_*.json"):
            phase_name = file.stem
            checkpoints.append(phase_name)

        return sorted(checkpoints)

    def clear_checkpoints(self):
        """Clear all checkpoints for this patient."""
        if self.checkpoint_dir.exists():
            for file in self.checkpoint_dir.glob("*.json"):
                file.unlink()
            print(f"✅ Cleared all checkpoints for {self.patient_id}")

    def checkpoint_exists(self, phase_name: str) -> bool:
        """Check if a checkpoint exists for the given phase."""
        checkpoint_file = self.checkpoint_dir / f"{phase_name}.json"
        return checkpoint_file.exists()


# Phase name constants for consistency
class Phase:
    """Phase names for checkpointing"""
    PHASE_0_WHO_CLASSIFICATION = "phase_0_who_classification"
    PHASE_1_DATA_LOADING = "phase_1_data_loading"
    PHASE_2_TIMELINE_CONSTRUCTION = "phase_2_timeline_construction"
    PHASE_2_5_TREATMENT_ORDINALITY = "phase_2_5_treatment_ordinality"
    PHASE_3_GAP_IDENTIFICATION = "phase_3_gap_identification"
    PHASE_4_BINARY_EXTRACTION = "phase_4_binary_extraction"
    PHASE_4_5_COMPLETENESS_ASSESSMENT = "phase_4_5_completeness_assessment"
    PHASE_5_PROTOCOL_VALIDATION = "phase_5_protocol_validation"
    PHASE_6_ARTIFACT_GENERATION = "phase_6_artifact_generation"

    @classmethod
    def all_phases(cls):
        """Return list of all phase names in order"""
        return [
            cls.PHASE_0_WHO_CLASSIFICATION,
            cls.PHASE_1_DATA_LOADING,
            cls.PHASE_2_TIMELINE_CONSTRUCTION,
            cls.PHASE_2_5_TREATMENT_ORDINALITY,
            cls.PHASE_3_GAP_IDENTIFICATION,
            cls.PHASE_4_BINARY_EXTRACTION,
            cls.PHASE_4_5_COMPLETENESS_ASSESSMENT,
            cls.PHASE_5_PROTOCOL_VALIDATION,
            cls.PHASE_6_ARTIFACT_GENERATION
        ]

    @classmethod
    def phase_index(cls, phase_name: str) -> int:
        """Get the index of a phase in the execution order"""
        try:
            return cls.all_phases().index(phase_name)
        except ValueError:
            return -1
