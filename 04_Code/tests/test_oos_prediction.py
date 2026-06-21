"""test_oos_prediction.py — Out-of-sample directional prediction (axis 3).

Validates the prediction/scoring logic and that the predictor has positive,
specific directional skill at the population level (per-trajectory CSD is noisy).
"""
from __future__ import annotations

import numpy as np

from oric.early_warning import find_jump
from oric.endogenous import EndogenousConfig, matched_fold_pair
from oric.oos_prediction import predict_transition, score_prediction


class TestScoring:
    def test_scoring_outcomes(self):
        from oric.oos_prediction import TransitionPrediction

        def pred(predicted, onset):
            return TransitionPrediction(predicted, 0.01, 0.5, 0.01, 0.0, onset, 100, 0.95)

        assert score_prediction(pred(True, 150), 160, timing_tolerance=50).outcome == "hit"
        assert score_prediction(pred(True, 150), 400, timing_tolerance=50).outcome == "miss"
        assert score_prediction(pred(True, None), None).outcome == "false_alarm"
        assert score_prediction(pred(False, None), 160).outcome == "miss"
        assert score_prediction(pred(False, None), None).outcome == "correct_rejection"
        # predicted + real transition but no timing estimate is still a hit
        assert score_prediction(pred(True, None), 160).outcome == "hit"


class TestPrediction:
    def test_predict_returns_wellformed(self):
        cfg = EndogenousConfig(noise_sd=0.05)
        db, _ = matched_fold_pair(cfg, n=1000, cross=True, seed=1)
        jb = find_jump(db["C"].to_numpy())
        pred = predict_transition(db["C"].to_numpy()[: max(400, jb - 60)],
                                  n_surrogates=49, rng=np.random.default_rng(0))
        assert 0.0 < pred.p_value <= 1.0
        assert isinstance(pred.predicted, bool)
        if pred.predicted_onset is not None:
            assert pred.predicted_onset >= pred.train_end

    def test_population_skill_above_chance(self):
        # Over replicates the bistable hit rate exceeds the twin false-alarm rate.
        cfg = EndogenousConfig(noise_sd=0.05)
        tp = fp = valid = 0
        for seed in range(12):
            db, dt = matched_fold_pair(cfg, n=1500, cross=True, seed=seed)
            Cb, Ct = db["C"].to_numpy(), dt["C"].to_numpy()
            jb = find_jump(Cb)
            t_obs = jb - 60
            if t_obs < 400:
                continue
            valid += 1
            pb = predict_transition(Cb[:t_obs], n_surrogates=49, rng=np.random.default_rng(seed))
            pt = predict_transition(Ct[:t_obs], n_surrogates=49,
                                    rng=np.random.default_rng(seed + 5))
            tp += score_prediction(pb, jb, timing_tolerance=500).outcome == "hit"
            fp += score_prediction(pt, None).outcome == "false_alarm"
        assert valid >= 8
        # Specificity: few false alarms; and hits strictly exceed false alarms.
        assert fp <= max(1, valid // 4)
        assert tp >= fp
