-- Seed Resources: Mumbai, Delhi, Bengaluru, Chennai, Hyderabad
-- 50+ resources across categories: hospital, police, shelter, ngo, mental_health, helpline, ambulance

-- ── AMBULANCE (national) ──────────────────────────────────────────────────────
INSERT INTO resources (name, category, phone, available_24x7, dispatchable, dispatch_type, city, state, lat, lng)
VALUES
  ('National Ambulance — iDAS 108', 'ambulance', '108', TRUE,  TRUE, 'phone', NULL, NULL, NULL, NULL),
  ('CATS Ambulance Delhi', 'ambulance', '102', TRUE, TRUE, 'phone', 'Delhi', 'Delhi', 28.6139, 77.2090),
  ('Mumbai Emergency Ambulance', 'ambulance', '1916', TRUE, TRUE, 'phone', 'Mumbai', 'Maharashtra', 19.0760, 72.8777);

-- ── POLICE (national) ─────────────────────────────────────────────────────────
INSERT INTO resources (name, category, phone, available_24x7, dispatchable, dispatch_type, city, state, lat, lng)
VALUES
  ('Emergency Police — 100', 'police', '100', TRUE, TRUE, 'phone', NULL, NULL, NULL, NULL),
  ('Women Helpline — 112', 'police', '112', TRUE, TRUE, 'phone', NULL, NULL, NULL, NULL);

-- ── HELPLINES (national) ──────────────────────────────────────────────────────
INSERT INTO resources (name, name_hi, category, phone, available_24x7, city, state, lat, lng, languages)
VALUES
  ('iCall Psychosocial Helpline', 'iCall मनोसामाजिक हेल्पलाइन',
   'helpline', '9152987821', FALSE, 'Mumbai', 'Maharashtra', 19.0330, 72.8654, '{hi,en}'),
  ('Vandrevala Foundation 24x7', 'वंद्रेवाला फाउंडेशन',
   'helpline', '1860-2662-345', TRUE, NULL, NULL, NULL, NULL, '{hi,en,mr,te,ta,kn,gu,bn,pa}'),
  ('iCall TISS', NULL,
   'helpline', '9152987821', FALSE, 'Mumbai', 'Maharashtra', 19.0240, 72.8456, '{hi,en}'),
  ('Snehi Helpline', 'स्नेही हेल्पलाइन',
   'helpline', '044-24640050', FALSE, 'Chennai', 'Tamil Nadu', 13.0827, 80.2707, '{ta,en}'),
  ('Aasra Suicide Prevention', 'आसरा',
   'helpline', '9820466627', TRUE, 'Navi Mumbai', 'Maharashtra', 19.0330, 73.0297, '{hi,en,mr}'),
  ('Sumaitri Delhi', 'सुमैत्री',
   'helpline', '011-23389090', FALSE, 'Delhi', 'Delhi', 28.6448, 77.2167, '{hi,en}'),
  ('Samaritans Mumbai', NULL,
   'helpline', '84229-84528', FALSE, 'Mumbai', 'Maharashtra', 19.0760, 72.8777, '{en}');

-- ── MENTAL HEALTH CENTRES — Mumbai ────────────────────────────────────────────
INSERT INTO resources (name, category, phone, city, state, lat, lng, address, hours, languages, available_24x7)
VALUES
  ('Nair Hospital Psychiatry OPD', 'mental_health', '022-23027500',
   'Mumbai', 'Maharashtra', 18.9646, 72.8333,
   'Dr. A.L. Nair Rd, Mumbai Central, Mumbai 400008', '8am–4pm Mon–Sat', '{hi,en,mr}', FALSE),
  ('KEM Hospital Psychiatry', 'mental_health', '022-24107000',
   'Mumbai', 'Maharashtra', 19.0022, 72.8381,
   'Acharya Donde Marg, Parel, Mumbai 400012', '8am–4pm Mon–Sat', '{hi,en,mr}', FALSE),
  ('Lokmanya Tilak Municipal Hospital', 'mental_health', '022-24076000',
   'Mumbai', 'Maharashtra', 19.0402, 72.8556,
   'Sion, Mumbai 400022', '24 hours', '{hi,en,mr}', TRUE),
  ('NIMHANS Satellite Centre Mumbai', 'mental_health', '022-22024000',
   'Mumbai', 'Maharashtra', 18.9350, 72.8259,
   'Colaba, Mumbai 400005', '9am–5pm Mon–Fri', '{hi,en,mr}', FALSE);

-- ── SHELTERS — Mumbai ─────────────────────────────────────────────────────────
INSERT INTO resources (name, name_hi, category, phone, city, state, lat, lng, address, available_24x7, capacity, languages)
VALUES
  ('Snehi Shelter Mumbai', 'स्नेही आश्रय मुंबई', 'shelter', '022-23821999',
   'Mumbai', 'Maharashtra', 19.0547, 72.8409,
   'Dharavi, Mumbai 400017', TRUE, 40, '{hi,en,mr}'),
  ('Majlis Saathi House', 'मजलिस साथी हाउस', 'shelter', '022-23821999',
   'Mumbai', 'Maharashtra', 18.9685, 72.8344,
   'Byculla, Mumbai 400027', FALSE, 25, '{hi,en,ur}'),
  ('Swadhar Greh Andheri', 'स्वाधार ग्रेह अंधेरी', 'shelter', '022-26364444',
   'Mumbai', 'Maharashtra', 19.1197, 72.8467,
   'Andheri East, Mumbai 400069', TRUE, 30, '{hi,en,mr,gu}'),
  ('iWatch Foundation Shelter', NULL, 'shelter', '022-27735511',
   'Mumbai', 'Maharashtra', 19.1767, 72.9556,
   'Thane, Maharashtra 400601', FALSE, 20, '{hi,en,mr}');

-- ── HOSPITALS — Mumbai ────────────────────────────────────────────────────────
INSERT INTO resources (name, category, phone, city, state, lat, lng, address, available_24x7)
VALUES
  ('Cooper Hospital Mumbai', 'hospital', '022-26208575',
   'Mumbai', 'Maharashtra', 19.0923, 72.8396,
   'NS Rd, Juhu, Vile Parle West, Mumbai 400056', TRUE),
  ('Jaslok Hospital', 'hospital', '022-66573333',
   'Mumbai', 'Maharashtra', 18.9707, 72.8122,
   '15, Dr. G. Deshmukh Marg, Mumbai 400026', TRUE),
  ('Hinduja Hospital', 'hospital', '022-24452222',
   'Mumbai', 'Maharashtra', 19.0052, 72.8348,
   'Veer Savarkar Marg, Mahim, Mumbai 400016', TRUE);

-- ── DELHI resources ────────────────────────────────────────────────────────────
INSERT INTO resources (name, name_hi, category, phone, city, state, lat, lng, address, available_24x7, hours, languages)
VALUES
  ('AIIMS Psychiatry Delhi', 'AIIMS मनोचिकित्सा', 'mental_health', '011-26588888',
   'Delhi', 'Delhi', 28.5672, 77.2100,
   'Sri Aurobindo Marg, Ansari Nagar, New Delhi 110029', FALSE, '8am–4pm Mon–Sat', '{hi,en}'),
  ('NIMHANS Delhi OPD', NULL, 'mental_health', '011-23807000',
   'Delhi', 'Delhi', 28.6448, 77.2167,
   'Ansari Nagar, New Delhi 110029', FALSE, '9am–5pm Mon–Fri', '{hi,en}'),
  ('Shakti Shalini Delhi Shelter', 'शक्ति शालिनी', 'shelter', '011-24373734',
   'Delhi', 'Delhi', 28.6277, 77.2190,
   'New Delhi 110001', TRUE, 35, '{hi,en,pu}'),
  ('Jagori Safe House Delhi', 'जागोरी', 'shelter', '011-26692700',
   'Delhi', 'Delhi', 28.5494, 77.1799,
   'Vasant Kunj, New Delhi 110070', FALSE, 20, '{hi,en}'),
  ('RML Hospital Delhi', 'RML अस्पताल', 'hospital', '011-23365525',
   'Delhi', 'Delhi', 28.6354, 77.2046,
   'Baba Kharak Singh Marg, New Delhi 110001', TRUE, NULL, '{hi,en}'),
  ('Safdarjung Hospital', 'सफदरजंग अस्पताल', 'hospital', '011-26707444',
   'Delhi', 'Delhi', 28.5672, 77.2083,
   'Safdarjung, New Delhi 110029', TRUE, NULL, '{hi,en}'),
  ('Hauz Khas Police Station', NULL, 'police', '011-26863700',
   'Delhi', 'Delhi', 28.5433, 77.2066,
   'Hauz Khas, New Delhi 110016', TRUE, NULL, '{hi,en}');

-- ── BENGALURU resources ───────────────────────────────────────────────────────
INSERT INTO resources (name, category, phone, city, state, lat, lng, address, available_24x7, hours, languages)
VALUES
  ('NIMHANS Bengaluru', 'mental_health', '080-46110007',
   'Bengaluru', 'Karnataka', 12.9415, 77.5978,
   'Hosur Rd, Lakkasandra, Bengaluru 560029', FALSE, '9am–5pm Mon–Fri', '{kn,en,hi,ta,te}'),
  ('St. John''s Hospital Psychiatry', 'hospital', '080-22065000',
   'Bengaluru', 'Karnataka', 12.9379, 77.6249,
   'Sarjapur Rd, Koramangala, Bengaluru 560034', TRUE, NULL, '{kn,en,hi,ta}'),
  ('Vandrevala Foundation Crisis', 'helpline', '1860-2662-345',
   'Bengaluru', 'Karnataka', 12.9716, 77.5946,
   'Bengaluru service area', TRUE, NULL, '{kn,en,hi,ta,te}'),
  ('Parihar Shelter Bengaluru', 'shelter', '080-22237489',
   'Bengaluru', 'Karnataka', 12.9785, 77.6408,
   'Indira Nagar, Bengaluru 560038', TRUE, 30, '{kn,en,hi,ta}'),
  ('Victoria Hospital Bengaluru', 'hospital', '080-22282121',
   'Bengaluru', 'Karnataka', 12.9636, 77.5724,
   'Fort Rd, Bhavani Nagar, Bengaluru 560002', TRUE, NULL, '{kn,en,hi,ta}');

-- ── CHENNAI resources ─────────────────────────────────────────────────────────
INSERT INTO resources (name, category, phone, city, state, lat, lng, address, available_24x7, hours, languages)
VALUES
  ('NIMHANS TN Centre', 'mental_health', '044-26140001',
   'Chennai', 'Tamil Nadu', 13.0343, 80.2443,
   'Kilpauk, Chennai 600010', FALSE, '9am–5pm Mon–Fri', '{ta,en,hi,te}'),
  ('Institute of Mental Health Chennai', 'mental_health', '044-26411600',
   'Chennai', 'Tamil Nadu', 13.0679, 80.2785,
   'Kilpauk, Chennai 600010', TRUE, '24 hours', '{ta,en,hi}'),
  ('Government General Hospital Chennai', 'hospital', '044-25305000',
   'Chennai', 'Tamil Nadu', 13.0799, 80.2826,
   'Park Town, Chennai 600003', TRUE, NULL, '{ta,en,hi,te,ml}'),
  ('Anbagam Shelter Chennai', 'shelter', '044-24640050',
   'Chennai', 'Tamil Nadu', 13.0620, 80.2785,
   'Kilpauk, Chennai 600010', TRUE, 25, '{ta,en,hi}');

-- ── HYDERABAD resources ───────────────────────────────────────────────────────
INSERT INTO resources (name, category, phone, city, state, lat, lng, address, available_24x7, hours, languages)
VALUES
  ('NIMHANS Hyderabad', 'mental_health', '040-23264161',
   'Hyderabad', 'Telangana', 17.4290, 78.3558,
   'Erragadda, Hyderabad 500018', FALSE, '9am–5pm Mon–Fri', '{te,en,hi,ur}'),
  ('Osmania General Hospital', 'hospital', '040-24601116',
   'Hyderabad', 'Telangana', 17.3712, 78.4815,
   'Afzalgunj, Hyderabad 500012', TRUE, NULL, '{te,en,hi,ur}'),
  ('Prajwala Shelter Hyderabad', 'shelter', '040-23543050',
   'Hyderabad', 'Telangana', 17.4343, 78.4071,
   'Banjara Hills, Hyderabad 500034', TRUE, 40, '{te,en,hi,ur}'),
  ('Vandrevala Hyderabad', 'helpline', '1860-2662-345',
   'Hyderabad', 'Telangana', 17.3850, 78.4867,
   'Hyderabad service area', TRUE, NULL, '{te,en,hi,ur}');

-- ── NGO resources (multi-city) ────────────────────────────────────────────────
INSERT INTO resources (name, name_hi, category, phone, whatsapp, city, state, available_24x7, hours, languages)
VALUES
  ('iCall — TISS Counselling', 'iCall - TISS', 'ngo', '9152987821', '9152987821',
   'Mumbai', 'Maharashtra', FALSE, 'Mon–Sat 8am–10pm', '{hi,en,mr,gu}'),
  ('Parivarthan Counselling', NULL, 'ngo', '76766-03555',
   NULL, 'Bengaluru', 'Karnataka', FALSE, 'Mon–Sat 9am–9pm', '{kn,en,hi,ta}'),
  ('Minds Foundation', 'माइंड्स फाउंडेशन', 'ngo', '9167030606',
   '9167030606', 'Mumbai', 'Maharashtra', FALSE, 'Mon–Fri 9am–6pm', '{hi,en,mr}'),
  ('The Y P Foundation', NULL, 'ngo', '011-41539020',
   NULL, 'Delhi', 'Delhi', FALSE, 'Mon–Fri 10am–6pm', '{hi,en}');

-- ── Pharmacy (24hr) ───────────────────────────────────────────────────────────
INSERT INTO resources (name, category, phone, city, state, lat, lng, available_24x7)
VALUES
  ('Apollo Pharmacy 24hr Mumbai', 'pharmacy', '1800-419-0075', 'Mumbai', 'Maharashtra', 19.0760, 72.8777, TRUE),
  ('MedPlus Delhi 24hr', 'pharmacy', '1800-419-0175', 'Delhi', 'Delhi', 28.6139, 77.2090, TRUE),
  ('Apollo Pharmacy 24hr Bengaluru', 'pharmacy', '1800-419-0075', 'Bengaluru', 'Karnataka', 12.9716, 77.5946, TRUE);
