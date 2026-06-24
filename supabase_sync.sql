-- Run this in Supabase Dashboard → SQL Editor → New Query
-- Adds the two new employees and reactivates two inactive ones

INSERT INTO employees (employee_code, organization, sponsor, arabic_name, position, department, section, default_project_id, hiring_date, basic_salary, net_salary, gross_salary, new_net_salary, new_allowance, new_net_earning, insurance_salary_base, status, notes, created_at)
VALUES
('129029', 'AFM', 'Professional', 'طه عبدالله سعدونى متولى', 'HVAC Technician', 'Maintenance', 'Mechanical',
 (SELECT project_id FROM projects WHERE project_name = 'Chevron' LIMIT 1),
 '2026-06-07', 0, 0, 0, 10000, 0, 10000, 0, 'Active', '', NOW()),
('129030', 'AFM', 'Professional', 'عمر خالد عزالدين عمر سليمان', 'Janitor', 'Services', 'Housekeeping',
 (SELECT project_id FROM projects WHERE project_name = 'Chevron Upstream' LIMIT 1),
 '2026-06-07', 0, 0, 0, 5539.83, 1642.94, 7182.77, 0, 'Active', '', NOW())
ON CONFLICT(employee_code) DO NOTHING;

UPDATE employees SET status = 'Active', updated_at = NOW() WHERE employee_code IN ('126383', '124139');
