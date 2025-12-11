"""
CLI version of Kobo-99 iCal generator.
Generates kobo99.ics into docs/ folder for GitHub Pages publishing.
"""

import logging
import os
import sys
from kobo_ical.service import Kobo99ICalService

OUTPUT_DIR = "docs"
OUTPUT_FILE = "kobo99.ics"

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


def ensure_output_dir():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)


def main():
    print("🔄 Generating Kobo 99 iCal (.ics) file...")
    print(f"Current working directory: {os.getcwd()}")

    ensure_output_dir()
    print(f"Output directory '{OUTPUT_DIR}' ensured")

    # 在 GitHub Actions 中啟用隨機延遲
    use_random_delay = os.getenv("GITHUB_ACTIONS") == "true"
    print(f"Random delay enabled: {use_random_delay}")

    try:
        service = Kobo99ICalService()
        print("Service initialized, starting to generate ICS...")
        ical_data = service.generate_ical(use_random_delay=use_random_delay)
        # 生成清理後資料
        cleaned = service.clean_existing_data()
        print(f"Cleaned items: {len(cleaned)} written to {service.settings.path_cleaned}")
        
        if not ical_data:
            print("⚠️ Warning: ICS data is empty!")
            sys.exit(1)
        
        print(f"ICS data generated, length: {len(ical_data)} characters")
    except Exception as e:
        print(f"❌ Failed to generate ICS: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    output_path = os.path.join(OUTPUT_DIR, OUTPUT_FILE)
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(ical_data)
        print(f"✅ ICS file written successfully: {output_path}")
        
        # 驗證檔案是否存在且有內容
        if os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            print(f"✅ File exists, size: {file_size} bytes")
            if file_size == 0:
                print("⚠️ Warning: File is empty!")
        else:
            print("❌ Error: File was not created!")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Failed to write ICS file: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
