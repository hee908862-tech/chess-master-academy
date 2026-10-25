# Historical full regression collection and merge blockers

See [expanded-regression.md](expanded-regression.md) for the subsequently authorized repair and verification work. Counts below describe their named historical runs, not the current head.

The local batch completed without maxfail: **1,140 passed, 131 failed, 7 skipped** in 3,865.08 seconds. It began before commit a6a8fc3, so its failures include seven board-feedback expectations subsequently fixed and verified in the final **73-pass** focused run. The added logout test is also in that focused run, not in this earlier collection. Do not describe this batch as an exact-head green run.

## Classification

1. **Introduced packaging regression, now fixed:** `test_copy_covers_local_runtime_imports` found `basic_clips` missing from the explicit Docker COPY. The Dockerfile now includes it. Isolated COPY payload smoke imports the actual module and generates all three reported scene clips. Packaging plus clip rules: **55 passed** in 32.37 seconds. This is payload validation, not a Docker image build.
2. **Confirmed legacy UI expectations:** pending/save text and SVG relation renderer assertions were stale on main; corrected while retaining state, duplicate-submit, geometry, cleanup and no-write checks. Other observed stale expectations include opening selectors inside closed disclosures, foundation course buttons inside a collapsed course list, exact `view active` classes despite the existing additional `flow-returning` class, and old visible home sections now placed in an archive disclosure. These remaining tests are not blanket-skipped or weakened.
3. **Confirmed existing display defect:** `test_late_old_diagnosis_read_does_not_reverse_progress` reaches subskill question 2/4 while the home model shows initial-course 0/48. Reproduced on main 0e28cad with product code unchanged and only the test entry helper adapted to the current retained-course entry. The helper was restored afterward. `test_prerequisite_cached_card_waits_for_read_then_focuses_without_writes` also fails at the same collapsed-list assertion on unchanged main; further investigation is needed to distinguish its contract/timing issue from a product defect. No score/data-model changes were made to suppress these failures.
4. **Local environment:** Stockfish is absent; configured package download returned HTTP 403. The batch includes explicit missing-engine failures and seven preexisting engine-conditional skips. CI installs Stockfish and retains those assertions. This work adds no skip or xfail.

Unclassified failures below need individual investigation; their presence is not proof that all are preexisting product defects. The previously corrected scoped-result recommendation mismatch is documented in README and its regression assertions remain enabled.

## CI and release gate

Exact-head a6a8fc3 full collection: https://github.com/hee908862-tech/chess-master-academy/actions/runs/40196071313 . It completed with 1,159 passed and 120 failed. The packaging-fix head d0f5c94 also completed with 1,159 passed and 120 failed (run 40199322217); its packaging test passed, while two timing-dependent browser assertions appeared in place of the packaging and CP-fixture failures. Merge remains prohibited until the final head passes; no merge or manual deployment has occurred. Render Live was reconfirmed at `0e28cadd9f8d8800ec6dd63d3c48bf8b7f1f135e` (`dep-dbdhvgtg1s2s73dm5pr0`).

Raw local evidence: `/tmp/chess-batched-full.log`, `/tmp/chess-full-failures.txt`, `/tmp/clip-final-focused.log`, `/tmp/clip-package-final.log`, `/tmp/baseline-extra-failures.log`, `/tmp/baseline-progress-confirmed.log`. The last baseline reproduction changes the test helper only, not product code. Physical Kakao/iOS remains untested.

## Local failure inventory by module

| Module | Failures |
| --- | ---: |
| `tests/test_attempt_review.py` | 1 |
| `tests/test_board_feedback_browser.py` | 7 |
| `tests/test_board_motion_wiring_browser.py` | 1 |
| `tests/test_board_presentation_browser.py` | 3 |
| `tests/test_diagnosis_alternatives.py` | 2 |
| `tests/test_diagnosis_progress_conflict_browser.py` | 1 |
| `tests/test_education_browser.py` | 2 |
| `tests/test_entry_followup_browser.py` | 2 |
| `tests/test_evidence_flow_browser.py` | 9 |
| `tests/test_evidence_navigation_followup.py` | 7 |
| `tests/test_feature_navigation_browser.py` | 3 |
| `tests/test_first_visit_browser.py` | 17 |
| `tests/test_focus_interface_browser.py` | 6 |
| `tests/test_focused_learning_browser.py` | 8 |
| `tests/test_focused_learning_followup.py` | 3 |
| `tests/test_followup_browser.py` | 4 |
| `tests/test_foundations_browser.py` | 7 |
| `tests/test_game_analysis.py` | 2 |
| `tests/test_game_restore_feedback.py` | 1 |
| `tests/test_growth_real_browser.py` | 1 |
| `tests/test_guest_practice_browser.py` | 3 |
| `tests/test_home_foundation_followup.py` | 2 |
| `tests/test_image_runtime_package.py` | 1 |
| `tests/test_initial_accessibility_browser.py` | 1 |
| `tests/test_journey_browser.py` | 4 |
| `tests/test_learning_pagination.py` | 2 |
| `tests/test_midwidth_focus.py` | 3 |
| `tests/test_primary_contrast_browser.py` | 3 |
| `tests/test_progress_followup_browser.py` | 1 |
| `tests/test_redesign_browser_followup.py` | 1 |
| `tests/test_redesign_selection.py` | 1 |
| `tests/test_repertoire_browser.py` | 2 |
| `tests/test_responsive_qa.py` | 8 |
| `tests/test_review_context_feedback.py` | 2 |
| `tests/test_rules_entry_cycle_browser.py` | 1 |
| `tests/test_study.py` | 1 |
| `tests/test_visual_evidence_browser.py` | 8 |

## Complete local failure names

- `tests/test_attempt_review.py::test_actual_stockfish_agrees_with_short_mate_counterexample`
- `tests/test_board_feedback_browser.py::test_real_training_pending_completion_stable_board_controls[320-800-1]`
- `tests/test_board_feedback_browser.py::test_real_training_pending_completion_stable_board_controls[390-844-1]`
- `tests/test_board_feedback_browser.py::test_real_training_pending_completion_stable_board_controls[1280-720-1]`
- `tests/test_board_feedback_browser.py::test_real_training_pending_completion_stable_board_controls[844-390-1]`
- `tests/test_board_feedback_browser.py::test_real_training_pending_completion_stable_board_controls[1280-720-2]`
- `tests/test_board_feedback_browser.py::test_training_failure_requires_authoritative_refresh`
- `tests/test_board_feedback_browser.py::test_fact_visibility_position_cleanup_and_no_writes`
- `tests/test_board_motion_wiring_browser.py::test_foundation_real_intermediate_and_final_delta`
- `tests/test_board_presentation_browser.py::test_current_check_label_cleanup_and_opening_history_motion`
- `tests/test_board_presentation_browser.py::test_real_opening_api_checkmate_display_and_black_orientation_capture[390]`
- `tests/test_board_presentation_browser.py::test_real_opening_api_checkmate_display_and_black_orientation_capture[1280]`
- `tests/test_diagnosis_alternatives.py::test_ozelq_real_engine_and_sequence_context`
- `tests/test_diagnosis_alternatives.py::test_balanced_api_real_ozelq_and_busy_reason`
- `tests/test_diagnosis_progress_conflict_browser.py::test_late_old_diagnosis_read_does_not_reverse_progress`
- `tests/test_education_browser.py::test_delayed_write_account_or_screen_exit_no_stale_render[False]`
- `tests/test_education_browser.py::test_prerequisite_cached_card_waits_for_read_then_focuses_without_writes`
- `tests/test_entry_followup_browser.py::test_entry_complete_practice_then_direct_standard_choice[balanced-24]`
- `tests/test_entry_followup_browser.py::test_entry_complete_practice_then_direct_standard_choice[quick-12]`
- `tests/test_evidence_flow_browser.py::test_home_one_next_step_with_explicit_estimate[new-\ub098\uc758`
- `tests/test_evidence_flow_browser.py::test_home_one_next_step_with_explicit_estimate[active-\uc800\uc7a5\ub41c`
- `tests/test_evidence_flow_browser.py::test_home_one_next_step_with_explicit_estimate[training-\uc9c4\ud589`
- `tests/test_evidence_flow_browser.py::test_home_one_next_step_with_explicit_estimate[incomplete-\ucd94\ucc9c`
- `tests/test_evidence_flow_browser.py::test_home_one_next_step_with_explicit_estimate[unlocked-\uc0c8`
- `tests/test_evidence_flow_browser.py::test_home_one_next_step_with_explicit_estimate[retention-7\uc77c`
- `tests/test_evidence_flow_browser.py::test_home_one_next_step_with_explicit_estimate[preparing-\uc900\ube44`
- `tests/test_evidence_flow_browser.py::test_home_one_next_step_with_explicit_estimate[error-\uc800\uc7a5`
- `tests/test_evidence_flow_browser.py::test_pc_disclosure_tab_leaves_without_navigation`
- `tests/test_evidence_navigation_followup.py::test_rules_first_home_action_reaches_recommended_basics`
- `tests/test_evidence_navigation_followup.py::test_home_primary_destination[active-diagnosis]`
- `tests/test_evidence_navigation_followup.py::test_home_primary_destination[training-training]`
- `tests/test_evidence_navigation_followup.py::test_home_primary_destination[retention-diagnosis]`
- `tests/test_evidence_navigation_followup.py::test_previous_account_delayed_report_cannot_replace_current_home`
- `tests/test_evidence_navigation_followup.py::test_menu_short_height_text_enlargement_and_width_transition[900-420-1]`
- `tests/test_evidence_navigation_followup.py::test_menu_short_height_text_enlargement_and_width_transition[1280-480-1.5]`
- `tests/test_feature_navigation_browser.py::test_navigation_help_no_mutations_and_opening_layout[390]`
- `tests/test_feature_navigation_browser.py::test_navigation_help_no_mutations_and_opening_layout[1280]`
- `tests/test_feature_navigation_browser.py::test_study_promotion_cancel_restores_board_controls`
- `tests/test_first_visit_browser.py::test_fresh_trial_keyboard_skip_reload_no_server_writes`
- `tests/test_first_visit_browser.py::test_signup_from_trial_starts_real_first_step_without_transferring_success`
- `tests/test_first_visit_browser.py::test_existing_login_keeps_saved_activity_and_cancel_is_safe`
- `tests/test_first_visit_browser.py::test_guest_layout_and_all_destinations_require_auth[1366-768]`
- `tests/test_first_visit_browser.py::test_guest_layout_and_all_destinations_require_auth[360-800]`
- `tests/test_first_visit_browser.py::test_guest_layout_and_all_destinations_require_auth[320-640]`
- `tests/test_first_visit_browser.py::test_guest_layout_and_all_destinations_require_auth[844-390]`
- `tests/test_first_visit_browser.py::test_cancel_late_login_cannot_replace_new_account_or_start_old_path`
- `tests/test_first_visit_browser.py::test_login_error_cancel_and_zoom`
- `tests/test_first_visit_browser.py::test_delayed_foundations_after_signup_does_not_start_after_leaving[False]`
- `tests/test_first_visit_browser.py::test_delayed_foundations_after_signup_does_not_start_after_leaving[True]`
- `tests/test_first_visit_browser.py::test_returning_action_precedes_optional_guides_and_group_location`
- `tests/test_first_visit_browser.py::test_skip_prioritizes_activities_and_preserves_revisit_preference`
- `tests/test_first_visit_browser.py::test_late_logout_cannot_clear_new_login_and_failure_preserves_account`
- `tests/test_first_visit_browser.py::test_entry_primary_contrast_initial_skip_and_returning`
- `tests/test_first_visit_browser.py::test_trial_continue_label_matches_authentication[False]`
- `tests/test_first_visit_browser.py::test_trial_continue_label_matches_authentication[True]`
- `tests/test_focus_interface_browser.py::test_foundation_focused_bounds_and_readonly_details[size0]`
- `tests/test_focus_interface_browser.py::test_foundation_focused_bounds_and_readonly_details[size1]`
- `tests/test_focus_interface_browser.py::test_foundation_focused_bounds_and_readonly_details[size2]`
- `tests/test_focus_interface_browser.py::test_foundation_focused_bounds_and_readonly_details[size3]`
- `tests/test_focus_interface_browser.py::test_foundation_focused_bounds_and_readonly_details[size4]`
- `tests/test_focus_interface_browser.py::test_foundation_focused_bounds_and_readonly_details[size5]`
- `tests/test_focused_learning_browser.py::test_home_foundation_practice_list_history_no_writes[320-800]`
- `tests/test_focused_learning_browser.py::test_home_foundation_practice_list_history_no_writes[390-844]`
- `tests/test_focused_learning_browser.py::test_home_foundation_practice_list_history_no_writes[485-757]`
- `tests/test_focused_learning_browser.py::test_home_foundation_practice_list_history_no_writes[1280-720]`
- `tests/test_focused_learning_browser.py::test_hub_home_mobile_and_menu_does_not_change_selected_piece`
- `tests/test_focused_learning_browser.py::test_list_focus_counts_and_485_geometry`
- `tests/test_focused_learning_browser.py::test_guest_foundation_login_route_and_ephemeral_trial_reload`
- `tests/test_focused_learning_browser.py::test_late_foundation_start_does_not_leave_hub`
- `tests/test_focused_learning_followup.py::test_home_has_one_foundation_entry_with_real_progress[new]`
- `tests/test_focused_learning_followup.py::test_home_has_one_foundation_entry_with_real_progress[basics]`
- `tests/test_focused_learning_followup.py::test_home_has_one_foundation_entry_with_real_progress[diagnosis]`
- `tests/test_followup_browser.py::test_guest_return_and_board_layout[1366-768]`
- `tests/test_followup_browser.py::test_guest_return_and_board_layout[1165-747]`
- `tests/test_followup_browser.py::test_guest_return_and_board_layout[390-844]`
- `tests/test_followup_browser.py::test_guest_return_and_board_layout[844-390]`
- `tests/test_foundations_browser.py::test_rules_route_saved_progress_layout_and_keyboard[320-640]`
- `tests/test_foundations_browser.py::test_rules_route_saved_progress_layout_and_keyboard[400-860]`
- `tests/test_foundations_browser.py::test_rules_route_saved_progress_layout_and_keyboard[1280-900]`
- `tests/test_foundations_browser.py::test_promotion_judgement_retry_and_choice_changes`
- `tests/test_foundations_browser.py::test_all_authored_steps_with_real_board_and_judgement_controls`
- `tests/test_foundations_browser.py::test_unstarted_vs_started_zero_progress_and_visible_recommendation[320-640]`
- `tests/test_foundations_browser.py::test_unstarted_vs_started_zero_progress_and_visible_recommendation[1280-900]`
- `tests/test_game_analysis.py::test_actual_stockfish_terminal_mate_is_not_low_depth`
- `tests/test_game_analysis.py::test_actual_stockfish_stalemate_is_terminal_not_missing_depth`
- `tests/test_game_restore_feedback.py::test_stale_read_cannot_replace_newer_read_or_account`
- `tests/test_growth_real_browser.py::test_solved_partial_diagnosis_five_tasks_resume_and_concept_path`
- `tests/test_guest_practice_browser.py::test_guest_examples_are_ephemeral_and_do_not_write[390]`
- `tests/test_guest_practice_browser.py::test_guest_examples_are_ephemeral_and_do_not_write[1280]`
- `tests/test_guest_practice_browser.py::test_guest_load_failure_retry_and_late_exit_are_readonly`
- `tests/test_home_foundation_followup.py::test_home_label_destination_and_no_mutation[new-390]`
- `tests/test_home_foundation_followup.py::test_home_label_destination_and_no_mutation[new-1180]`
- `tests/test_image_runtime_package.py::test_copy_covers_local_runtime_imports`
- `tests/test_initial_accessibility_browser.py::test_keyboard_rotation_zoom_and_history_keep_active_session`
- `tests/test_journey_browser.py::test_journey_partial_resume_result_training[1366-768]`
- `tests/test_journey_browser.py::test_journey_partial_resume_result_training[390-844]`
- `tests/test_journey_browser.py::test_real_journey_complete_skipped_then_training[1366-768-pc]`
- `tests/test_journey_browser.py::test_real_journey_complete_skipped_then_training[390-844-mobile]`
- `tests/test_learning_pagination.py::test_older_card_next_problem_uses_completed_category`
- `tests/test_learning_pagination.py::test_more_button_double_click_and_late_page_after_refresh`
- `tests/test_midwidth_focus.py::test_midwidth_board_and_primary_completion_actions[foundation]`
- `tests/test_midwidth_focus.py::test_midwidth_board_and_primary_completion_actions[training]`
- `tests/test_midwidth_focus.py::test_midwidth_board_and_primary_completion_actions[guest]`
- `tests/test_primary_contrast_browser.py::test_main_actions_contrast_keyboard_and_narrow_layout[320-800]`
- `tests/test_primary_contrast_browser.py::test_main_actions_contrast_keyboard_and_narrow_layout[1280-720]`
- `tests/test_primary_contrast_browser.py::test_foundation_waiting_error_reason_and_primary_disabled_style`
- `tests/test_progress_followup_browser.py::test_past_lazy_evidence_is_read_only_during_active_diagnosis`
- `tests/test_redesign_browser_followup.py::test_diagnosis_repeat_selection_preserves_session[1366-768]`
- `tests/test_redesign_selection.py::test_repeated_selection_cancels_and_friendly_selection_switches`
- `tests/test_repertoire_browser.py::test_chained_action_stale_completion_cannot_start_or_close[False-finish]`
- `tests/test_repertoire_browser.py::test_chained_action_stale_completion_cannot_start_or_close[False-hint]`
- `tests/test_responsive_qa.py::test_responsive_boards_long_copy_and_last_result[320]`
- `tests/test_responsive_qa.py::test_responsive_boards_long_copy_and_last_result[360]`
- `tests/test_responsive_qa.py::test_responsive_boards_long_copy_and_last_result[390]`
- `tests/test_responsive_qa.py::test_responsive_boards_long_copy_and_last_result[430]`
- `tests/test_responsive_qa.py::test_responsive_boards_long_copy_and_last_result[768]`
- `tests/test_responsive_qa.py::test_responsive_boards_long_copy_and_last_result[900]`
- `tests/test_responsive_qa.py::test_responsive_boards_long_copy_and_last_result[1024]`
- `tests/test_responsive_qa.py::test_responsive_boards_long_copy_and_last_result[1280]`
- `tests/test_review_context_feedback.py::test_review_owner_changes_on_real_login_and_late_analysis_is_ignored[False]`
- `tests/test_review_context_feedback.py::test_review_owner_changes_on_real_login_and_late_analysis_is_ignored[True]`
- `tests/test_rules_entry_cycle_browser.py::test_rules_entry_offer_resumes_existing_diagnosis`
- `tests/test_study.py::test_exploration_preserves_all_account_state_and_actual_engine`
- `tests/test_visual_evidence_browser.py::test_auto_en_passant_skip_routes_and_readonly_replay[1366-768]`
- `tests/test_visual_evidence_browser.py::test_auto_en_passant_skip_routes_and_readonly_replay[1180-650]`
- `tests/test_visual_evidence_browser.py::test_auto_en_passant_skip_routes_and_readonly_replay[360-800]`
- `tests/test_visual_evidence_browser.py::test_auto_en_passant_skip_routes_and_readonly_replay[390-844]`
- `tests/test_visual_evidence_browser.py::test_auto_en_passant_skip_routes_and_readonly_replay[844-390]`
- `tests/test_visual_evidence_browser.py::test_check_mate_arrows_and_square_explanation`
- `tests/test_visual_evidence_browser.py::test_complete_domain_radar_replay_analysis_and_readonly_state`
- `tests/test_visual_evidence_browser.py::test_reduced_motion_setting_preserves_en_passant_and_new_state`
