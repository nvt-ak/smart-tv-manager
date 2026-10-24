"""APK metadata & signature analysis."""
import hashlib
import os
from typing import Any, Dict

try:
    from androguard.misc import AnalyzeAPK
except Exception:
    AnalyzeAPK = None


class ApkAnalyzer:
    def analyze(self, apk_path: str) -> Dict[str, Any]:
        result = {
            "path": apk_path,
            "filename": os.path.basename(apk_path),
            "size": os.path.getsize(apk_path) if os.path.exists(apk_path) else 0,
            "sha256": self._sha256(apk_path),
        }
        if AnalyzeAPK and os.path.exists(apk_path):
            try:
                a, d, dx = AnalyzeAPK(apk_path)
                result["package"] = a.get_package()
                result["version_name"] = a.get_androidversion_name()
                result["version_code"] = a.get_androidversion_code()
                result["min_sdk"] = a.get_min_sdk_version()
                result["target_sdk"] = a.get_target_sdk_version()
                perms = a.get_permissions() or []
                result["permissions"] = sorted(list(perms))
                dangerous_keywords = ["CAMERA", "RECORD_AUDIO", "MICROPHONE", "ACCESS_FINE_LOCATION", "ACCESS_COARSE_LOCATION", "READ_CONTACTS", "READ_SMS", "SEND_SMS", "READ_CALL_LOG", "READ_PHONE_STATE", "WRITE_EXTERNAL_STORAGE", "READ_EXTERNAL_STORAGE"]
                result["dangerous_count"] = len([p for p in perms if any(k in p for k in dangerous_keywords)])
                try:
                    certs = a.get_certificates()
                    result["certs_count"] = len(certs)
                    if certs:
                        c = certs[0]
                        try:
                            result["cert_issuer"] = str(c.issuer)[:120]
                            result["cert_subject"] = str(c.subject)[:120]
                        except Exception:
                            pass
                        try:
                            result["cert_serial"] = str(c.serial_number)
                        except Exception:
                            pass
                except Exception:
                    pass
            except Exception as e:
                result["error"] = str(e)
        return result

    def _sha256(self, path: str) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
