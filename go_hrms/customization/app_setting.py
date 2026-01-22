import frappe
from frappe import get_url

@frappe.whitelist()
def upload_logo_and_set():
    """
    Upload logo and set it in the app settings.
    """
    from frappe.utils.file_manager import save_file
    
    file_name = "go-150-170.png"
    folder = "Home/Attachments"
    logo_image_path = "./assets/go_hrms/images/" + file_name

    # Check if the logo is already set in System Settings or if the file exists in attachments
    if frappe.db.get_value("System Settings", None, "logo") or \
       frappe.db.exists("File", {"file_name": file_name, "folder": folder}):
        return

    # Upload the logo image
    try:
        frappe.flags.mute_messages = True

        with open(logo_image_path, "rb") as f:
            file_data = f.read()

            file_doc = save_file(
                fname=file_name, 
                content=file_data,
                dt=None,
                dn=None,
                folder=folder,
                is_private=0
            )
            logo_url = file_doc.file_url
            
            # Set values in System Settings and Website Settings
            frappe.db.set_value("System Settings", None, "logo", logo_url)
            
            website_settings = frappe.get_doc("Website Settings", "Website Settings")
            website_settings.app_logo = logo_url 
            website_settings.splash_image = logo_url
            website_settings.favicon = logo_url
            website_settings.app_name = "Go-Smart HRMS Suite"
            website_settings.website_theme = "Standard"

            try:
                website_settings.save(ignore_permissions=True)
                # commit the transaction and clear cache
                frappe.db.commit()
                frappe.clear_cache()
                print(f"Logo uploaded successfully and set in Website Settings: {logo_url}")
            except Exception as e:
                print("Failed to update Website Settings: " + str(e))
    
    except Exception as e:
        print("Failed to upload logo: " + str(e))
    finally: 
        frappe.flags.mute_messages = False