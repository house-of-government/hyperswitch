"""Mutation checks for the deliberately narrow source-rule audit, not Idric tests."""
import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('type_contract_audit', HERE / 'check_types.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class SourceAuditTests(unittest.TestCase):
    def setUp(self):
        self.original_root = audit.ROOT
        self.temporary = tempfile.TemporaryDirectory()
        audit.ROOT = Path(self.temporary.name)
        shutil.copytree(self.original_root / 'HyperSwitch', audit.ROOT / 'HyperSwitch')
        (audit.ROOT / '_/tests').mkdir(parents=True)
        for name in ('type_baseline.json', 'type_rejections.json'):
            shutil.copy2(HERE / name, audit.ROOT / '_/tests' / name)

    def tearDown(self):
        audit.ROOT = self.original_root
        self.temporary.cleanup()

    def test_complete_baseline(self):
        result = audit.source_audit()
        self.assertEqual(result['source_comparisons'], 5803)
        self.assertEqual(result['indexed_capability_constructors'], 39)
        self.assertEqual(len(audit.rejection_cases()), 45)

    def test_mutations_are_rejected(self):
        mutations = [
            ('Connector', 'access_token_support (trustpay, bank_transfer)', 'access_token_support (trustpay, card)'),
            ('Connector', 'access_token_support_for (trustpay, bank_transfer) = Just Trustpay_transfer_token', 'access_token_support_for (trustpay, bank_transfer) = Just Trustpay_redirect_token'),
            ('Connector', 'supports_access_token provider method = capability_present (access_token_support_for (provider, method))', 'supports_access_token provider method = True'),
            ('Connector', '(0 capability : access_token_support selection)', '(capability : access_token_support selection)'),
            ('Connector', 'Maybe (AccessTokenPlan selection)', 'Maybe Bool'),
            ('Connector', 'Just capability ⇒ Just (MkAccessTokenPlan selection capability)', 'Just capability ⇒ Nothing'),
            ('PaymentMethod', 'Inactive_to_active : payment_method_transition (payment_method_inactive, payment_method_active)', 'Inactive_to_active : payment_method_transition (payment_method_active, payment_method_inactive)'),
            ('PaymentMethod', 'locker_id_policy_for (wallet, lookup_saved_customer_method) = omit_locker_id', 'locker_id_policy_for (wallet, lookup_saved_customer_method) = persist_locker_id'),
            ('PaymentMethod', '(0 permitted : payment_method_transition edge)', '(permitted : Bool)'),
            ('PaymentMethod', '%default total', '%default partial'),
        ]
        for module, before, after in mutations:
            with self.subTest(mutation=before):
                path = audit.ROOT / 'HyperSwitch' / (module + '.idric')
                original = path.read_text()
                self.assertIn(before, original)
                path.write_text(original.replace(before, after, 1))
                try:
                    with self.assertRaises(ValueError):
                        audit.source_audit()
                finally:
                    path.write_text(original)


if __name__ == '__main__':
    unittest.main()
