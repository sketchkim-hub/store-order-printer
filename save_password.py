# (고급) Firebase 계정 비밀번호를 Windows 자격 증명 관리자에 저장. 보통은 [설정] > 온라인 동기화 에서 입력하면 됩니다.
import getpass, json, os, keyring, appconfig
p = os.path.join(appconfig.data_dir(), "firebase_config.json")
c = json.load(open(p, encoding="utf-8"))
keyring.set_password("festival-receipt", c["email"], getpass.getpass(c["email"] + " 비밀번호: "))
print("저장 완료.")
