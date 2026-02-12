"""Tests for services.api.chat_job_state_machine module."""

from __future__ import annotations

import unittest

from services.api.chat_job_state_machine import (
    ChatJobStateMachine,
    can_requeue_chat_job,
    is_terminal_chat_job_status,
    normalize_chat_job_status,
    transition_chat_job_status,
)


class TestNormalizeChatJobStatus(unittest.TestCase):
    """normalize_chat_job_status converts to lowercase stripped string."""

    def test_none_returns_queued(self):
        self.assertEqual(normalize_chat_job_status(None), "queued")

    def test_empty_string_returns_queued(self):
        self.assertEqual(normalize_chat_job_status(""), "queued")

    def test_whitespace_only_returns_queued(self):
        self.assertEqual(normalize_chat_job_status("   "), "queued")

    def test_case_normalization(self):
        self.assertEqual(normalize_chat_job_status("Processing"), "processing")
        self.assertEqual(normalize_chat_job_status("DONE"), "done")

    def test_strips_whitespace(self):
        self.assertEqual(normalize_chat_job_status("  failed  "), "failed")


class TestCanRequeueChatJob(unittest.TestCase):
    """can_requeue_chat_job returns True only for active statuses."""

    def test_queued_is_requeuable(self):
        self.assertTrue(can_requeue_chat_job("queued"))

    def test_processing_is_requeuable(self):
        self.assertTrue(can_requeue_chat_job("processing"))

    def test_done_not_requeuable(self):
        self.assertFalse(can_requeue_chat_job("done"))

    def test_failed_not_requeuable(self):
        self.assertFalse(can_requeue_chat_job("failed"))

    def test_cancelled_not_requeuable(self):
        self.assertFalse(can_requeue_chat_job("cancelled"))


class TestIsTerminalChatJobStatus(unittest.TestCase):
    """is_terminal_chat_job_status returns True only for terminal statuses."""

    def test_done_is_terminal(self):
        self.assertTrue(is_terminal_chat_job_status("done"))

    def test_failed_is_terminal(self):
        self.assertTrue(is_terminal_chat_job_status("failed"))

    def test_cancelled_is_terminal(self):
        self.assertTrue(is_terminal_chat_job_status("cancelled"))

    def test_queued_not_terminal(self):
        self.assertFalse(is_terminal_chat_job_status("queued"))

    def test_processing_not_terminal(self):
        self.assertFalse(is_terminal_chat_job_status("processing"))


class TestChatJobStateMachineTransitions(unittest.TestCase):
    """ChatJobStateMachine.transition validates against _TRANSITIONS."""

    def test_queued_to_processing(self):
        sm = ChatJobStateMachine("queued")
        self.assertEqual(sm.transition("processing"), "processing")

    def test_processing_to_done(self):
        sm = ChatJobStateMachine("processing")
        self.assertEqual(sm.transition("done"), "done")

    def test_queued_to_failed(self):
        sm = ChatJobStateMachine("queued")
        self.assertEqual(sm.transition("failed"), "failed")

    def test_queued_to_cancelled(self):
        sm = ChatJobStateMachine("queued")
        self.assertEqual(sm.transition("cancelled"), "cancelled")

    def test_processing_to_failed(self):
        sm = ChatJobStateMachine("processing")
        self.assertEqual(sm.transition("failed"), "failed")

    # --- invalid transitions ---

    def test_queued_to_done_raises(self):
        sm = ChatJobStateMachine("queued")
        with self.assertRaises(ValueError):
            sm.transition("done")

    def test_processing_to_queued_raises(self):
        sm = ChatJobStateMachine("processing")
        with self.assertRaises(ValueError):
            sm.transition("queued")

    def test_done_to_queued_raises(self):
        sm = ChatJobStateMachine("done")
        with self.assertRaises(ValueError):
            sm.transition("queued")

    def test_done_to_processing_raises(self):
        sm = ChatJobStateMachine("done")
        with self.assertRaises(ValueError):
            sm.transition("processing")

    # --- self-loops on terminal statuses ---

    def test_done_self_loop(self):
        sm = ChatJobStateMachine("done")
        self.assertEqual(sm.transition("done"), "done")

    def test_failed_self_loop(self):
        sm = ChatJobStateMachine("failed")
        self.assertEqual(sm.transition("failed"), "failed")

    def test_cancelled_self_loop(self):
        sm = ChatJobStateMachine("cancelled")
        self.assertEqual(sm.transition("cancelled"), "cancelled")

    # --- unknown status ---

    def test_unknown_current_status_raises(self):
        sm = ChatJobStateMachine.__new__(ChatJobStateMachine)
        sm.status = "bogus"
        with self.assertRaises(ValueError):
            sm.transition("queued")


class TestTransitionChatJobStatusConvenience(unittest.TestCase):
    """transition_chat_job_status is a convenience wrapper."""

    def test_valid_transition(self):
        self.assertEqual(transition_chat_job_status("queued", "processing"), "processing")

    def test_invalid_transition_raises(self):
        with self.assertRaises(ValueError):
            transition_chat_job_status("done", "queued")


if __name__ == "__main__":
    unittest.main()
