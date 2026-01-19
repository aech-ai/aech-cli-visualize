"""Dashboard composer with VLM validation feedback loop."""

import logging
from pathlib import Path
from typing import Any

from ..utils.export import FormatType
from ..validation import (
    CorrectionEngine,
    LayoutCorrection,
    RenderResult,
    ValidationResult,
    VLMValidator,
)
from .composer import DashboardComposer


logger = logging.getLogger(__name__)


class ValidatedDashboardComposer:
    """Dashboard composer with VLM validation and correction loop."""

    def __init__(
        self,
        spec: dict[str, Any],
        theme: str | dict[str, Any] = "corporate",
        enable_vlm_validation: bool = True,
        max_iterations: int = 3,
        vlm_model: str | None = None,
    ):
        """Initialize the validated composer.

        Args:
            spec: Dashboard specification
            theme: Theme name or dictionary
            enable_vlm_validation: Whether to use VLM validation loop
            max_iterations: Maximum render/validate iterations
            vlm_model: VLM model identifier (e.g., "openai:gpt-4o")
        """
        self.spec = spec
        self.theme = theme
        self.enable_vlm_validation = enable_vlm_validation
        self.max_iterations = max_iterations

        self.validator = VLMValidator(model=vlm_model) if enable_vlm_validation else None
        self.correction_engine = CorrectionEngine()

    def render(
        self,
        output_dir: str | Path,
        filename: str = "dashboard",
        format: FormatType = "png",
        resolution: str = "1080p",
        scale: float = 2.0,
    ) -> RenderResult:
        """Render dashboard with optional VLM validation loop.

        Args:
            output_dir: Directory to write output file
            filename: Base filename (without extension)
            format: Output format (png, svg, pdf)
            resolution: Resolution preset or WxH
            scale: Scale factor for higher DPI

        Returns:
            RenderResult with path, iterations, and validation history
        """
        output_dir = Path(output_dir)

        # If VLM validation disabled, do single render
        if not self.enable_vlm_validation or self.validator is None:
            return self._render_without_validation(
                output_dir, filename, format, resolution, scale
            )

        # VLM validation loop
        return self._render_with_validation(
            output_dir, filename, format, resolution, scale
        )

    def _render_without_validation(
        self,
        output_dir: Path,
        filename: str,
        format: FormatType,
        resolution: str,
        scale: float,
    ) -> RenderResult:
        """Render without VLM validation (existing behavior)."""
        composer = DashboardComposer(spec=self.spec, theme=self.theme)
        output_path = composer.render(
            output_dir=output_dir,
            filename=filename,
            format=format,
            resolution=resolution,
            scale=scale,
        )

        return RenderResult(
            path=output_path,
            iterations=1,
            validation_history=None,
            final_spec=self.spec,
            corrections_applied=[],
        )

    def _render_with_validation(
        self,
        output_dir: Path,
        filename: str,
        format: FormatType,
        resolution: str,
        scale: float,
    ) -> RenderResult:
        """Render with VLM validation and correction loop."""
        current_spec = self.spec.copy()
        validation_history: list[ValidationResult] = []
        all_corrections: list[LayoutCorrection] = []
        iteration = 0
        output_path: Path | None = None
        vlm_error: str | None = None

        while iteration < self.max_iterations:
            # Render with current spec
            iter_filename = f"{filename}_iter{iteration}" if iteration > 0 else filename
            composer = DashboardComposer(spec=current_spec, theme=self.theme)

            try:
                output_path = composer.render(
                    output_dir=output_dir,
                    filename=iter_filename,
                    format=format,
                    resolution=resolution,
                    scale=scale,
                )
            except Exception as e:
                logger.error(f"Render failed at iteration {iteration}: {e}")
                raise

            # Validate with VLM
            try:
                result = self.validator.evaluate(output_path, current_spec)  # type: ignore
                validation_history.append(result)
            except Exception as e:
                logger.warning(f"VLM validation failed: {e}")
                vlm_error = str(e)
                break

            # Check if acceptable
            if result.is_acceptable:
                logger.info(f"Dashboard approved after {iteration + 1} iteration(s)")
                break

            # Check for divergence
            if self._is_diverging(validation_history):
                logger.warning("Corrections not improving - stopping early")
                break

            # Compute and apply corrections
            corrections = self.correction_engine.compute_corrections(result, current_spec)

            if not corrections:
                logger.info("No further corrections available")
                break

            # Apply corrections
            current_spec = self.correction_engine.apply_corrections(current_spec, corrections)
            all_corrections.extend(corrections)

            logger.info(
                f"Iteration {iteration + 1}: Applied {len(corrections)} correction(s), "
                f"{len(result.issues)} issue(s) detected"
            )

            iteration += 1

        # Determine final status
        warning = None
        if validation_history and not validation_history[-1].is_acceptable:
            if iteration >= self.max_iterations:
                warning = f"Max iterations ({self.max_iterations}) reached without full approval"
            else:
                warning = "Validation loop ended with remaining issues"

        return RenderResult(
            path=output_path or Path(output_dir) / f"{filename}.{format}",
            iterations=iteration + 1,
            validation_history=validation_history,
            final_spec=current_spec,
            corrections_applied=all_corrections,
            warning=warning,
            vlm_error=vlm_error,
        )

    def _is_diverging(self, history: list[ValidationResult]) -> bool:
        """Check if corrections are making things worse.

        Args:
            history: List of validation results from each iteration

        Returns:
            True if we appear to be stuck or regressing
        """
        if len(history) < 2:
            return False

        recent = history[-1]
        previous = history[-2]

        # If issue count increased, we might be diverging
        if len(recent.issues) > len(previous.issues):
            return True

        # If same number of issues and same types, we're stuck
        if len(recent.issues) == len(previous.issues):
            recent_types = {(i.issue_type, tuple(i.affected_widgets)) for i in recent.issues}
            prev_types = {(i.issue_type, tuple(i.affected_widgets)) for i in previous.issues}
            if recent_types == prev_types:
                return True

        return False
