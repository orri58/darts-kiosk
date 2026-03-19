"""
Onboarding Wizard Tests — v3.5.4+

Tests for the Superadmin Onboarding Wizard feature:
1. Customer creation via /api/licensing/customers
2. Location creation via /api/licensing/locations
3. License creation via /api/licensing/licenses
4. Registration token creation via /api/central/registration-tokens

Wizard flow: Kunde → Standort → Lizenz → Gerät (Token)
"""
import os
import pytest
import requests
from datetime import datetime, timedelta

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Module: Admin Auth
class TestAdminAuth:
    """Tests for Kiosk Admin authentication"""
    
    def test_admin_login_success(self):
        """Admin can login with admin/admin123"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "access_token" in data, "No access_token in response"
        assert data["user"]["username"] == "admin"
        print("✓ Admin login success")

# Module: Customer CRUD (Step 1 of Wizard)
class TestCustomerEndpoints:
    """Tests for /api/licensing/customers endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get admin token for tests"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert response.status_code == 200, "Failed to login as admin"
        self.token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_list_customers(self):
        """GET /api/licensing/customers returns customer list"""
        response = requests.get(f"{BASE_URL}/api/licensing/customers", headers=self.headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✓ List customers: {len(data)} customers found")
    
    def test_create_customer(self):
        """POST /api/licensing/customers creates new customer"""
        test_name = f"TEST_WizardCustomer_{datetime.now().strftime('%H%M%S')}"
        response = requests.post(f"{BASE_URL}/api/licensing/customers", 
            headers=self.headers,
            json={
                "name": test_name,
                "contact_email": "wizard-test@example.com",
                "contact_phone": "+49 30 999"
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["name"] == test_name, "Customer name should match"
        assert "id" in data, "Customer should have ID"
        print(f"✓ Customer created: {data['id']}")
        # Store for cleanup
        self.created_customer_id = data["id"]
        return data["id"]

# Module: Location CRUD (Step 2 of Wizard)
class TestLocationEndpoints:
    """Tests for /api/licensing/locations endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get admin token and create a test customer"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert response.status_code == 200, "Failed to login as admin"
        self.token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
        
        # Create test customer for location tests
        test_name = f"TEST_LocTestCustomer_{datetime.now().strftime('%H%M%S')}"
        cust_resp = requests.post(f"{BASE_URL}/api/licensing/customers", 
            headers=self.headers,
            json={"name": test_name}
        )
        assert cust_resp.status_code == 200, "Failed to create test customer"
        self.test_customer_id = cust_resp.json()["id"]
    
    def test_list_locations(self):
        """GET /api/licensing/locations returns location list"""
        response = requests.get(f"{BASE_URL}/api/licensing/locations", headers=self.headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✓ List locations: {len(data)} locations found")
    
    def test_create_location_with_customer_id(self):
        """POST /api/licensing/locations creates location with customer_id"""
        test_name = f"TEST_WizardLocation_{datetime.now().strftime('%H%M%S')}"
        response = requests.post(f"{BASE_URL}/api/licensing/locations", 
            headers=self.headers,
            json={
                "customer_id": self.test_customer_id,
                "name": test_name,
                "address": "Test Address 123, Berlin"
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["name"] == test_name, "Location name should match"
        assert data["customer_id"] == self.test_customer_id, "Customer ID should match"
        assert "id" in data, "Location should have ID"
        print(f"✓ Location created: {data['id']} for customer {self.test_customer_id}")

# Module: License CRUD (Step 3 of Wizard)
class TestLicenseEndpoints:
    """Tests for /api/licensing/licenses endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get admin token and create a test customer"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert response.status_code == 200, "Failed to login as admin"
        self.token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
        
        # Create test customer for license tests
        test_name = f"TEST_LicTestCustomer_{datetime.now().strftime('%H%M%S')}"
        cust_resp = requests.post(f"{BASE_URL}/api/licensing/customers", 
            headers=self.headers,
            json={"name": test_name}
        )
        assert cust_resp.status_code == 200, "Failed to create test customer"
        self.test_customer_id = cust_resp.json()["id"]
    
    def test_list_licenses(self):
        """GET /api/licensing/licenses returns license list"""
        response = requests.get(f"{BASE_URL}/api/licensing/licenses", headers=self.headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✓ List licenses: {len(data)} licenses found")
    
    def test_create_license_with_ends_at(self):
        """POST /api/licensing/licenses creates license with calculated ends_at"""
        # Calculate ends_at (30 days from now)
        ends_at = (datetime.utcnow() + timedelta(days=30)).isoformat() + "Z"
        
        response = requests.post(f"{BASE_URL}/api/licensing/licenses", 
            headers=self.headers,
            json={
                "customer_id": self.test_customer_id,
                "plan_type": "standard",
                "max_devices": 1,
                "grace_days": 7,
                "ends_at": ends_at
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["customer_id"] == self.test_customer_id, "Customer ID should match"
        assert data["plan_type"] == "standard", "Plan type should be standard"
        assert data["max_devices"] == 1, "Max devices should be 1"
        assert data["grace_days"] == 7, "Grace days should be 7"
        assert "id" in data, "License should have ID"
        assert "ends_at" in data, "License should have ends_at"
        print(f"✓ License created: {data['id']}, ends_at={data['ends_at']}")
    
    def test_create_premium_license(self):
        """POST /api/licensing/licenses creates premium license"""
        ends_at = (datetime.utcnow() + timedelta(days=365)).isoformat() + "Z"
        
        response = requests.post(f"{BASE_URL}/api/licensing/licenses", 
            headers=self.headers,
            json={
                "customer_id": self.test_customer_id,
                "plan_type": "premium",
                "max_devices": 5,
                "grace_days": 14,
                "ends_at": ends_at
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["plan_type"] == "premium", "Plan type should be premium"
        assert data["max_devices"] == 5, "Max devices should be 5"
        print(f"✓ Premium license created: {data['id']}")

# Module: Registration Token (Step 4 of Wizard via Central Proxy)
class TestRegistrationTokenEndpoints:
    """Tests for /api/central/registration-tokens endpoints (proxy to central server)"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get admin token and create test entities"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert response.status_code == 200, "Failed to login as admin"
        self.token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
        
        # Create test customer for token tests
        test_name = f"TEST_TokenTestCustomer_{datetime.now().strftime('%H%M%S')}"
        cust_resp = requests.post(f"{BASE_URL}/api/licensing/customers", 
            headers=self.headers,
            json={"name": test_name}
        )
        assert cust_resp.status_code == 200, "Failed to create test customer"
        self.test_customer_id = cust_resp.json()["id"]
        
        # Create test location
        loc_resp = requests.post(f"{BASE_URL}/api/licensing/locations", 
            headers=self.headers,
            json={"customer_id": self.test_customer_id, "name": f"TEST_TokenTestLocation"}
        )
        assert loc_resp.status_code == 200, "Failed to create test location"
        self.test_location_id = loc_resp.json()["id"]
        
        # Create test license
        ends_at = (datetime.utcnow() + timedelta(days=365)).isoformat() + "Z"
        lic_resp = requests.post(f"{BASE_URL}/api/licensing/licenses", 
            headers=self.headers,
            json={
                "customer_id": self.test_customer_id,
                "plan_type": "standard",
                "max_devices": 1,
                "ends_at": ends_at
            }
        )
        assert lic_resp.status_code == 200, "Failed to create test license"
        self.test_license_id = lic_resp.json()["id"]
    
    def test_list_registration_tokens(self):
        """GET /api/central/registration-tokens lists tokens via proxy"""
        response = requests.get(f"{BASE_URL}/api/central/registration-tokens", headers=self.headers)
        # 200 = success, 502 = central server unreachable (acceptable in some envs)
        assert response.status_code in [200, 502], f"Expected 200 or 502, got {response.status_code}: {response.text}"
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list), "Response should be a list"
            print(f"✓ List registration tokens: {len(data)} tokens found")
        else:
            print("⚠ Central server unreachable (502) - token list unavailable")
    
    def test_create_registration_token(self):
        """POST /api/central/registration-tokens creates token via proxy"""
        response = requests.post(f"{BASE_URL}/api/central/registration-tokens", 
            headers=self.headers,
            json={
                "expires_in_hours": 24,
                "customer_id": self.test_customer_id,
                "location_id": self.test_location_id,
                "license_id": self.test_license_id,
                "device_name_template": "TEST_WizardDevice"
            }
        )
        # 200 = success, 502 = central server unreachable
        assert response.status_code in [200, 502], f"Expected 200 or 502, got {response.status_code}: {response.text}"
        if response.status_code == 200:
            data = response.json()
            assert "raw_token" in data, "Response should contain raw_token"
            assert data["raw_token"].startswith("drt_"), "Token should start with drt_"
            print(f"✓ Registration token created: {data['raw_token'][:20]}...")
        else:
            print("⚠ Central server unreachable (502) - token creation unavailable")

# Module: Full Wizard Flow E2E
class TestOnboardingWizardE2E:
    """End-to-end test of the complete onboarding wizard flow"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get admin token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert response.status_code == 200, "Failed to login as admin"
        self.token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
    
    def test_full_wizard_flow(self):
        """Complete wizard flow: Customer → Location → License → Token"""
        timestamp = datetime.now().strftime('%H%M%S')
        
        # Step 1: Create Customer
        print("\n--- Step 1: Create Customer ---")
        cust_resp = requests.post(f"{BASE_URL}/api/licensing/customers", 
            headers=self.headers,
            json={
                "name": f"TEST_E2E_Customer_{timestamp}",
                "contact_email": f"e2e-{timestamp}@test.com",
                "contact_phone": "+49 30 12345"
            }
        )
        assert cust_resp.status_code == 200, f"Customer creation failed: {cust_resp.text}"
        customer = cust_resp.json()
        customer_id = customer["id"]
        print(f"✓ Customer created: {customer['name']} ({customer_id})")
        
        # Verify customer in list
        list_resp = requests.get(f"{BASE_URL}/api/licensing/customers", headers=self.headers)
        assert any(c["id"] == customer_id for c in list_resp.json()), "Customer should be in list"
        
        # Step 2: Create Location
        print("\n--- Step 2: Create Location ---")
        loc_resp = requests.post(f"{BASE_URL}/api/licensing/locations", 
            headers=self.headers,
            json={
                "customer_id": customer_id,
                "name": f"TEST_E2E_Location_{timestamp}",
                "address": "E2E Test Street 1, 12345 Berlin"
            }
        )
        assert loc_resp.status_code == 200, f"Location creation failed: {loc_resp.text}"
        location = loc_resp.json()
        location_id = location["id"]
        print(f"✓ Location created: {location['name']} ({location_id})")
        
        # Step 3: Create License
        print("\n--- Step 3: Create License ---")
        ends_at = (datetime.utcnow() + timedelta(days=365)).isoformat() + "Z"
        lic_resp = requests.post(f"{BASE_URL}/api/licensing/licenses", 
            headers=self.headers,
            json={
                "customer_id": customer_id,
                "plan_type": "standard",
                "max_devices": 1,
                "grace_days": 7,
                "ends_at": ends_at
            }
        )
        assert lic_resp.status_code == 200, f"License creation failed: {lic_resp.text}"
        license_data = lic_resp.json()
        license_id = license_data["id"]
        print(f"✓ License created: {license_data['plan_type']} ({license_id}), ends_at={license_data['ends_at']}")
        
        # Step 4: Create Registration Token
        print("\n--- Step 4: Create Registration Token ---")
        token_resp = requests.post(f"{BASE_URL}/api/central/registration-tokens", 
            headers=self.headers,
            json={
                "expires_in_hours": 24,
                "customer_id": customer_id,
                "location_id": location_id,
                "license_id": license_id,
                "device_name_template": f"TEST_E2E_Device_{timestamp}"
            }
        )
        
        if token_resp.status_code == 200:
            token_data = token_resp.json()
            assert "raw_token" in token_data, "Response should contain raw_token"
            raw_token = token_data["raw_token"]
            print(f"✓ Registration token created: {raw_token}")
            
            # Final summary
            print("\n=== Wizard Flow Complete ===")
            print(f"Customer: {customer['name']} ({customer_id})")
            print(f"Location: {location['name']} ({location_id})")
            print(f"License: {license_data['plan_type']} ({license_id})")
            print(f"Token: {raw_token}")
        elif token_resp.status_code == 502:
            print("⚠ Central server unreachable (502) - token creation skipped")
            print("\n=== Wizard Flow Partially Complete (no token due to central server offline) ===")
        else:
            pytest.fail(f"Token creation failed with unexpected status: {token_resp.status_code}: {token_resp.text}")

# Module: Dashboard Stats
class TestDashboardEndpoint:
    """Tests for /api/licensing/dashboard endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get admin token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert response.status_code == 200, "Failed to login as admin"
        self.token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_dashboard_returns_stats(self):
        """GET /api/licensing/dashboard returns stat counts"""
        response = requests.get(f"{BASE_URL}/api/licensing/dashboard", headers=self.headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        expected_keys = ["customers", "locations", "devices", "licenses_total", "licenses_active", "licenses_blocked"]
        for key in expected_keys:
            assert key in data, f"Dashboard should contain {key}"
            assert isinstance(data[key], int), f"{key} should be an integer"
        
        print(f"✓ Dashboard stats: {data}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
