"""Tests ligeros de EvaluationLogger."""

import logging
import uuid

from utils.logger import EvaluationLogger


def test_logger_methods_do_not_raise():
    name = f"unit_test_{uuid.uuid4().hex[:8]}"
    el = EvaluationLogger(log_name=name)
    el.log_task_start("T", "Agent")
    el.log_task_progress("T", "msg")
    el.log_task_complete("T", "done")
    el.log_error("T", "err")
    el.log_email_sent("a@b.com", "subj", "success")
    el.log_email_sent("a@b.com", "subj", "fail")
    el.log_conversation_analysis("cid", "Cand", {"overall_score": 7})
    el.log_statistics({"k": 1})
    el.log_statistics({"a": 1, "b": 2})
    el.log_conversation_analysis("cid", "Cand", {})
    assert isinstance(el.logger, logging.Logger)
