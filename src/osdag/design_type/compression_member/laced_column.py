"""
Main module: Design of Compression Member
Sub-module:  Design of column (loaded axially)

@author:Sanket Gaikwad

Reference:
            1) IS 800: 2007 General construction in steel - Code of practice (Third revision)

"""
import logging
import math
import numpy as np
from PyQt5.QtWidgets import QTextEdit, QMessageBox, QLineEdit, QComboBox, QDialog, QVBoxLayout, QListWidget, QDialogButtonBox, QLabel
from PyQt5.QtCore import QObject, pyqtSignal
from ...Common import *
from ..connection.moment_connection import MomentConnection
from ...utils.common.material import *
from ...utils.common.load import Load
from ...utils.common.component import ISection, Material
from ...utils.common.component import *
from ..member import Member
from ...Report_functions import *
from ...utils.common.common_calculation import *
from ..tension_member import *
from ...utils.common.Section_Properties_Calculator import BBAngle_Properties, I_sectional_Properties, SHS_RHS_Properties, CHS_Properties
from ...utils.common import is800_2007
from ...design_report.reportGenerator_latex import CreateLatex
from ...Common import TYPE_TAB_4, TYPE_TAB_5 
from PyQt5.QtWidgets import QLineEdit, QMainWindow, QMessageBox
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QValidator, QDoubleValidator
from PyQt5.QtWidgets import QComboBox
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QFormLayout, QTableWidget, QTableWidgetItem, QListWidget, QHBoxLayout
from PyQt5.QtWidgets import QDialogButtonBox
import sqlite3
import os
import traceback
from ...utils.common.component import Material
from ...Common import KEY_LACING_SECTION_DIM

from .Column import ColumnDesign

class LacedColumn(ColumnDesign):
    '''
    def calculate_effective_length_yy(self, end_condition_1, end_condition_2, unsupported_length_yy):
        """
        Calculate the effective length (YY) using IS 800:2007 Table 11 logic.
        :param end_condition_1: End condition at one end (e.g., 'Fixed', 'Hinged', etc.)
        :param end_condition_2: End condition at other end
        :param unsupported_length_yy: Unsupported length in mm
        :return: Effective length in mm
        """
        # Table 11 typical K values (simplified)
        # Fixed-Fixed: 0.65, Fixed-Hinged: 0.8, Hinged-Hinged: 1.0, Fixed-Free: 2.0
        conds = {('Fixed', 'Fixed'): 0.65, ('Fixed', 'Hinged'): 0.8, ('Hinged', 'Fixed'): 0.8,
                 ('Hinged', 'Hinged'): 1.0, ('Fixed', 'Free'): 2.0, ('Free', 'Fixed'): 2.0}
        k = conds.get((end_condition_1, end_condition_2), 1.0)
        return k * unsupported_length_yy
    '''

    def print_all_section_results(self):
        """
        Print all calculated section results to the terminal for debugging and verification.
        """
        if hasattr(self, 'optimum_section_ur_results') and self.optimum_section_ur_results:
            print("\n[DEBUG] All calculated section results:")
            for ur, result in sorted(self.optimum_section_ur_results.items()):
                print(f"\nSection UR: {ur}")
                for k, v in result.items():
                    print(f"  {k}: {v}")
        else:
            print("[DEBUG] No section results available.")
    # --- Patch: Prevent application from quitting on minimize ---
    def event(self, event):
        # If the event is a window state change and the window is being minimized, ignore close/quit
        try:
            from PyQt5.QtCore import QEvent
            from PyQt5.QtWidgets import QApplication
            if event.type() == QEvent.WindowStateChange:
                if hasattr(self, 'window') and self.window is not None:
                    if self.window.isMinimized():
                        # Prevent quit/close on minimize
                        event.ignore()
                        return True
        except Exception as e:
            print('[DEBUG] Exception in minimize event patch:', e)
            pass
        return super().event(event)
    def calculate(self, design_dictionary):
        # Use the standard ColumnDesign workflow for calculation
        self.set_input_values(design_dictionary)
        self.section_classification()
        self.design_column()
        self.results()
        # Add lacing/tie-plate calculations
        self.calculate_lacing_and_tie_plate()

    def calculate_lacing_and_tie_plate(self):
        # Only the logic unique to laced columns (lacing/tie-plate calculations)
        if hasattr(self, 'section_property') and self.section_property is not None:
            self.tie_plate_d = round(2 * self.section_property.depth / 3, 2)         # mm
            self.tie_plate_t = round(self.section_property.web_thickness, 2)         # mm
            self.tie_plate_l = round(self.section_property.depth / 2, 2)             # mm
            self.channel_spacing = round(self.section_property.depth + 2 * self.tie_plate_t, 2)  # mm
            self.lacing_angle = round(math.degrees(math.atan(self.channel_spacing / (2 * self.tie_plate_l))), 2)  # degrees
            if not hasattr(self, 'result') or not isinstance(self.result, dict):
                self.result = {}
            self.result['tie_plate_d'] = self.tie_plate_d
            self.result['tie_plate_t'] = self.tie_plate_t
            self.result['tie_plate_l'] = self.tie_plate_l
            self.result['channel_spacing'] = self.channel_spacing
            self.result['lacing_spacing'] = self.lacing_angle

    def reset_output_state(self):
        self.effective_length_yy = None
        self.effective_length_zz = None
        self.effective_sr_yy = None
        self.effective_sr_zz = None
        self.result_fcd = None
        self.result_capacity = None
        self.result_UR = None
        self.result_section_class = None
        self.result_effective_area = None
        self.result_bc_yy = None
        self.result_bc_zz = None
        self.result_IF_yy = None
        self.result_IF_zz = None
        self.result_ebs_yy = None
        self.result_ebs_zz = None
        self.result_nd_esr_yy = None
        self.result_nd_esr_zz = None
        self.result_phi_yy = None
        self.result_phi_zz = None
        self.result_srf_yy = None
        self.result_srf_zz = None
        self.result_fcd_1_yy = None
        self.result_fcd_1_zz = None
        self.result_fcd_2 = None
        self.result_cost = None
        self.result = {}
        self.optimum_section_ur_results = {}
        # Any other custom/calculated fields should be reset here as well
    def __init__(self):
        super().__init__()
        # self.logger = logging.getLogger('Osdag')
        # self.logger.setLevel(logging.DEBUG)
        # handler = logging.StreamHandler()
        # formatter = logging.Formatter(fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        # handler.setFormatter(formatter)
        # self.logger.addHandler(handler)
        # handler = logging.FileHandler('logging_text.log')
        # self.logger.addHandler(handler)
        self.design_status = False
        self.failed_reason = None  # Track why design failed
        self.result = {}
        self.utilization_ratio = 0
        self.area = 0
        self.epsilon = 1.0
        self.fy = 0
        self.section = None
        self.material = {}
        self.weld_size = ''
        self.weld_type = ''
        self.weld_strength = 0
        self.lacing_incl_angle = 0
        self.lacing_section = ''
        self.lacing_type = ''
        self.allowed_utilization = ''
        self.module = KEY_DISP_COMPRESSION_LacedColumn
        self.mainmodule = 'Member'
        self.section_designation = None
        self.design_pref_dialog = None
        self.output_title_fields = {}
        self.double_validator = QDoubleValidator()
        self.double_validator.setNotation(QDoubleValidator.StandardNotation)
        self.double_validator.setDecimals(2)
        self.design_pref_dictionary = {
            KEY_DISP_LACEDCOL_WELD_SIZE: "5mm",
            KEY_DISP_LACEDCOL_BOLT_DIAMETER: "16mm",
            KEY_DISP_LACEDCOL_EFFECTIVE_AREA: "1.0",
            KEY_DISP_LACEDCOL_ALLOWABLE_UR: "1.0"
        }
        self.design_pref = {}  # Ensure design_pref is always defined
        # Define input line edits for unsupported lengths and axial load
        self.unsupported_length_yy_lineedit = QLineEdit()
        self.unsupported_length_zz_lineedit = QLineEdit()
        self.axial_load_lineedit = QLineEdit()
        # Define combo boxes for dropdowns
        self.material_combo = QComboBox()
        self.connection_combo = QComboBox()
        self.lacing_pattern_combo = QComboBox()
        self.section_profile_combo = QComboBox()
        self.section_designation_combo = QComboBox()
        self.flange_class = None
        self.web_class = None
        self.gamma_m0 = 1.1  # As per IS 800:2007, Table 5 for yield stress
        self.material_lookup_cache = {}  # Cache for (material, thickness) lookups

###############################################
# Design Preference Functions Start
###############################################
    def tab_list(self):
        """
        Returns list of tabs for design preferences, matching flexure.py exactly.
        """
        tabs = []
        # Column Section tab (use tab_section for flexure-like behavior)
        t1 = (KEY_DISP_COLSEC, TYPE_TAB_1, self.tab_section)
        tabs.append(t1)
        # Weld Preferences tab (keep as is)
        t2 = ("Weld Preferences", TYPE_TAB_4, self.all_weld_design_values)
        tabs.append(t2)
        return tabs

    def all_weld_design_values(self, *args):
        return [
            (KEY_DISP_LACEDCOL_LACING_PROFILE_TYPE, "Lacing Profile Type", TYPE_COMBOBOX, ["Angle", "Channel", "Flat"], True, 'No Validator'),
            (KEY_DISP_LACEDCOL_LACING_PROFILE, "Lacing Profile Section", TYPE_COMBOBOX_CUSTOMIZED, self.get_lacing_profiles, True, 'No Validator'),
            (KEY_DISP_LACEDCOL_EFFECTIVE_AREA, "Effective Area Parameter", TYPE_COMBOBOX, ["1.0", "0.9", "0.8", "0.7", "0.6", "0.5", "0.4", "0.3", "0.2", "0.1"], True, 'No Validator'),
            (KEY_DISP_LACEDCOL_ALLOWABLE_UR, "Allowable Utilization Ratio", TYPE_COMBOBOX, ["1.0", "0.95", "0.9", "0.85"], True, 'No Validator'),
            (KEY_DISP_LACEDCOL_BOLT_DIAMETER, "Bolt Diameter", TYPE_COMBOBOX, ["16mm", "20mm", "24mm", "27mm"], True, 'No Validator'),
            (KEY_DISP_LACEDCOL_WELD_SIZE, "Weld Size", TYPE_COMBOBOX, ["4mm", "5mm", "6mm", "8mm"], True, 'No Validator')
        ]

    def tab_value_changed(self):
        """
        Returns list of tuples for tab value changes, matching flexure.py exactly.
        """
        change_tab = []
        # Section material changes (auto-populate fu, fy)
        t1 = (KEY_DISP_COLSEC, [KEY_SEC_MATERIAL], [KEY_SEC_FU, KEY_SEC_FY], TYPE_TEXTBOX, self.get_fu_fy_I_section)
        change_tab.append(t1)
        # Section properties update (I-section properties)
        t2 = (KEY_DISP_COLSEC, ['Label_1', 'Label_2', 'Label_3', 'Label_4', 'Label_5'],
              ['Label_11', 'Label_12', 'Label_13', 'Label_14', 'Label_15', 'Label_16', 'Label_17', 'Label_18',
               'Label_19', 'Label_20', 'Label_21', 'Label_22', KEY_IMAGE], TYPE_TEXTBOX, self.get_I_sec_properties)
        change_tab.append(t2)
        # SHS/RHS properties update
        t3 = (KEY_DISP_COLSEC, ['Label_HS_1', 'Label_HS_2', 'Label_HS_3'],
              ['Label_HS_11', 'Label_HS_12', 'Label_HS_13', 'Label_HS_14', 'Label_HS_15', 'Label_HS_16', 'Label_HS_17', 'Label_HS_18',
               'Label_HS_19', 'Label_HS_20', 'Label_HS_21', 'Label_HS_22', KEY_IMAGE], TYPE_TEXTBOX, self.get_SHS_RHS_properties)
        change_tab.append(t3)
        # CHS properties update
        t4 = (KEY_DISP_COLSEC, ['Label_CHS_1', 'Label_CHS_2', 'Label_CHS_3'],
              ['Label_CHS_11', 'Label_CHS_12', 'Label_CHS_13', 'Label_HS_14', 'Label_HS_15', 'Label_HS_16', 'Label_21', 'Label_22',
               KEY_IMAGE], TYPE_TEXTBOX, self.get_CHS_properties)
        change_tab.append(t4)
        # Section source update (when section designation changes)
        t5 = (KEY_DISP_COLSEC, [KEY_SECSIZE], [KEY_SOURCE], TYPE_TEXTBOX, self.change_source)
        change_tab.append(t5)
        return change_tab

    def edit_tabs(self):
        """This function is required if the tab name changes based on connectivity or profile or any other key.
        Not required for this module but empty list should be passed"""
        return []

    def input_dictionary_design_pref(self):
        """
        Returns list of tuples for design preferences, matching flexure.py exactly.
        """
        design_input = []
        # Section material (combobox)
        t1 = (KEY_DISP_COLSEC, TYPE_COMBOBOX, [KEY_SEC_MATERIAL])
        design_input.append(t1)
        # Section properties (fu, fy)
        t2 = (KEY_DISP_COLSEC, TYPE_TEXTBOX, [KEY_SEC_FU, KEY_SEC_FY])
        design_input.append(t2)
        return design_input

    def input_dictionary_without_design_pref(self, *args, **kwargs):
        """
        Returns list of tuples for input dictionary without design preferences, matching flexure.py pattern.
        """
        design_input = []
        
        # Material input with safe defaults
        t1 = (KEY_MATERIAL, [KEY_SEC_MATERIAL], 'Input Dock')
        design_input.append(t1)

        # Weld preferences with safe defaults
        t2 = (None, [
                KEY_DISP_LACEDCOL_LACING_PROFILE_TYPE,
                KEY_DISP_LACEDCOL_LACING_PROFILE,
                KEY_DISP_LACEDCOL_EFFECTIVE_AREA,
                KEY_DISP_LACEDCOL_ALLOWABLE_UR,
                KEY_DISP_LACEDCOL_BOLT_DIAMETER,
                KEY_DISP_LACEDCOL_WELD_SIZE
            ], '')
        design_input.append(t2)

        return design_input

    def refresh_input_dock(self):
        """
        Returns list of tuples for refreshing input dock, matching flexure.py exactly.
        """
        add_buttons = []
        # Add section designation combobox for column section tab
        t1 = (KEY_DISP_COLSEC, KEY_SECSIZE, TYPE_COMBOBOX, KEY_SECSIZE, None, None, "Columns")
        add_buttons.append(t1)
        return add_buttons

    def get_values_for_design_pref(self, key, design_dictionary):
        """
        Returns default values for design preferences, matching flexure.py pattern.
        """
        if not design_dictionary or design_dictionary.get(KEY_MATERIAL, 'Select Material') == 'Select Material':
            fu = ''
            fy = ''
        else:
            material = Material(design_dictionary[KEY_MATERIAL], 41)
            fu = material.fu
            fy = material.fy

        val = {
            KEY_SECSIZE: 'Select Section',
            KEY_DISP_LACEDCOL_LACING_PROFILE_TYPE: "Angle",
            KEY_DISP_LACEDCOL_LACING_PROFILE: "ISA 40x40x5",
            KEY_DISP_LACEDCOL_EFFECTIVE_AREA: "1.0",
            KEY_DISP_LACEDCOL_ALLOWABLE_UR: "1.0",
            KEY_DISP_LACEDCOL_BOLT_DIAMETER: "16mm",
            KEY_DISP_LACEDCOL_WELD_SIZE: "5mm",
            KEY_SEC_FU: fu,
            KEY_SEC_FY: fy,
            KEY_SEC_MATERIAL: design_dictionary.get(KEY_MATERIAL, 'Select Material')
        }.get(key, '')

        return val

    def get_lacing_profiles(self, *args):
        """
        Returns lacing profile options based on selected lacing pattern.
        """
        if not args or not args[0]:
            return connectdb('Angles', call_type="popup")

        pattern = args[0]
        if pattern == "Angle":
            return connectdb('Angles', call_type="popup")
        elif pattern == "Channel":
            return connectdb('Channels', call_type="popup")
        elif pattern == "Flat":
            return connectdb('Channels', call_type="popup")
        else:
            return []

    ####################################
    # Design Preference Functions End
    ####################################

    # Setting up logger and Input and Output Docks
    ####################################
    def module_name(self):
        return KEY_DISP_COMPRESSION_COLUMN

    def set_osdaglogger(self, widget_or_key=None):
        import logging
        self.logger = logging.getLogger('Osdag')
        self.logger.setLevel(logging.DEBUG)
        handler = logging.StreamHandler()
        formatter = logging.Formatter(fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        handler = logging.FileHandler('logging_text.log')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        # Add QTextEdit logger if widget is provided
        if widget_or_key is not None and hasattr(widget_or_key, 'append'):
            class QTextEditLogger(logging.Handler):
                def __init__(self, text_edit):
                    super().__init__()
                    self.text_edit = text_edit
                def emit(self, record):
                    msg = self.format(record)
                    self.text_edit.append(msg)
            qtext_handler = QTextEditLogger(widget_or_key)
            qtext_handler.setFormatter(formatter)
            self.logger.addHandler(qtext_handler)
        elif widget_or_key is not None:
            # If it's a key, use your existing OurLog logic
            handler = OurLog(widget_or_key)
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    def customized_input(self, *args, **kwargs):
        c_lst = []
        # Section Designation ComboBox with All/Customized
        t1 = (KEY_SECSIZE, self.fn_section_designation)
        c_lst.append(t1)
        return c_lst

    def fn_section_designation(self, *args):
        # This function is called when the Section Size ComboBox (All/Customized) changes
        # args[0] is the selected profile, args[1] is 'All' or 'Customized'
        if len(args) == 1 and isinstance(args[0], list):
            args = args[0]
        profile = args[0] if len(args) > 0 else None
        mode = args[1] if len(args) > 1 else 'All'
        
        if mode == 'All':
            # Return all designations from DB for the selected profile
            result = self.fn_profile_section(profile)
            if not isinstance(result, list):
                result = [result] if result else []
            # self.logger.info(f"Section designation (All) for profile '{profile}': {result}")
            return result
        elif mode == 'Customized':
            # Open popup dialog for user to select
            # Fetch all designations for the selected profile from the database
            section_list = self.fn_profile_section(profile)
            if not section_list:
                return []
            # Patch: Only proceed if dialog is defined
            try:
                dialog = SectionDesignationDialog(section_list)
                if dialog.exec_() == QDialog.Accepted:
                    selected = dialog.get_selected()
                    if not isinstance(selected, list):
                        selected = [selected] if selected else []
                    return selected
                else:
                    current_selected = []  # Patch: fallback to empty list
                    return current_selected if current_selected else []
            except Exception:
                return []
        else:
            return []

    def open_section_designation_dialog(self, selected_profile, current_selected=None, disabled_values=None):
        if disabled_values is None:
            disabled_values = []
        section_list = connectdb(selected_profile, call_type="popup")
        dialog = SectionDesignationDialog(section_list)
        if current_selected:
            dialog.list_widget.clearSelection()
            for i in range(dialog.list_widget.count()):
                if dialog.list_widget.item(i).text() in current_selected:
                    dialog.list_widget.item(i).setSelected(True)
        if dialog.exec_() == QDialog.Accepted:
            selected = dialog.get_selected()
            self.sec_list = selected
            return selected
        return None

    def input_values(self, *args, **kwargs):
        """ 
        Function declared in ui_template.py line 566
        Function to return a list of tuples to be displayed as the UI (Input Dock)
        """
        self.module = KEY_DISP_LACEDCOL
        options_list = []

        # Module title and name
        options_list.append((KEY_DISP_LACEDCOL, "Laced Column", TYPE_MODULE, [], True, 'No Validator'))

        # Section
        options_list.append(("title_Section ", "Section Details", TYPE_TITLE, None, True, 'No Validator'))
        # Add section profile selection like in flexure.py
        options_list.append((KEY_SEC_PROFILE, KEY_DISP_SEC_PROFILE, TYPE_COMBOBOX, KEY_LACEDCOL_SEC_PROFILE_OPTIONS, True, 'No Validator'))
        # Section Designation ComboBox with All/Customized
        options_list.append((KEY_SECSIZE, KEY_DISP_SECSIZE, TYPE_COMBOBOX_CUSTOMIZED, ['All','Customized'], True, 'No Validator'))

        # Material
        options_list.append(("title_Material", "Material Properties", TYPE_TITLE, None, True, 'No Validator'))
        options_list.append((KEY_MATERIAL, KEY_DISP_MATERIAL, TYPE_COMBOBOX, VALUES_MATERIAL, True, 'No Validator'))

        # Geometry
        options_list.append(("title_Geometry", "Geometry", TYPE_TITLE, None, True, 'No Validator'))
        options_list.append((KEY_UNSUPPORTED_LEN_YY, KEY_DISP_UNSUPPORTED_LEN_YY, TYPE_TEXTBOX, None, True, 'Float Validator'))
        options_list.append((KEY_UNSUPPORTED_LEN_ZZ, KEY_DISP_UNSUPPORTED_LEN_ZZ, TYPE_TEXTBOX, None, True, 'Float Validator'))
        options_list.append((KEY_END1, KEY_DISP_END1, TYPE_COMBOBOX_CUSTOMIZED, VALUES_END1, True, 'No Validator'))
        options_list.append((KEY_END2,KEY_DISP_END2, TYPE_COMBOBOX_CUSTOMIZED, VALUES_END2, True, 'No Validator'))
        # Lacing
        options_list.append((KEY_LACING_PATTERN, "Lacing Pattern", TYPE_COMBOBOX, VALUES_LACING_PATTERN, True, 'No Validator'))
        # Connection
        options_list.append((KEY_CONN_TYPE, "Type of Connection", TYPE_COMBOBOX, VALUES_CONNECTION_TYPE, True, 'No Validator'))
        # Load
        options_list.append(("title_Load", "Load Details", TYPE_TITLE, None, True, 'No Validator'))
        options_list.append((KEY_AXIAL, "Axial Load (kN)", TYPE_TEXTBOX, None, True, 'Float Validator'))
        return options_list

    def fn_profile_section(self, *args):
        # Accepts either a list or *args
        if len(args) == 1 and isinstance(args[0], list):
            args = args[0]
        profile = args[0] if args else None
        
        # Handle laced column specific profiles
        if profile == '2-channels Back-to-Back':
            return connectdb("Channels", call_type="popup")
        elif profile == '2-channels Toe-to-Toe':
            return connectdb("Channels", call_type="popup")
        elif profile == '2-Girders':
            # For girders, we can use either Beams or Columns depending on the application
            res1 = connectdb("Beams", call_type="popup")
            res2 = connectdb("Columns", call_type="popup")
            return list(set(res1 + res2))
        # Handle standard profiles for backward compatibility
        elif profile == 'Beams':
            return connectdb("Beams", call_type="popup")
        elif profile == 'Columns':
            return connectdb("Columns", call_type="popup")
        elif profile == 'Beams and Columns':
            res1 = connectdb("Beams", call_type="popup")
            res2 = connectdb("Columns", call_type="popup")
            return list(set(res1 + res2))
        elif profile == 'RHS and SHS':
            res1 = connectdb("RHS", call_type="popup")
            res2 = connectdb("SHS", call_type="popup")
            return list(set(res1 + res2))
        elif profile == 'CHS':
            return connectdb("CHS", call_type="popup")
        elif profile in ['Angles', 'Back to Back Angles', 'Star Angles']:
            return connectdb('Angles', call_type="popup")
        elif profile in ['Channels', 'Back to Back Channels']:
            return connectdb("Channels", call_type="popup")
        else:
            # Default fallback - return empty list
            return []

    def fn_end1_end2(self, *args):
        if len(args) == 1 and isinstance(args[0], list):
            args = args[0]
        end1 = args[0] if args else None

        if end1 == 'Fixed':
            return VALUES_END2
        elif end1 == 'Free':
            return ['Fixed']
        elif end1 == 'Hinged':
            return ['Fixed', 'Hinged', 'Roller']
        elif end1 == 'Roller':
            return ['Fixed', 'Hinged']

    def fn_end1_image(self, *args):
        if len(args) == 1 and isinstance(args[0], list):
            args = args[0]
        val = args[0] if args else None
        if val == 'Fixed':
            return str(files("osdag.data.ResourceFiles.images").joinpath("6.RRRR.PNG"))
        elif val == 'Free':
            return str(files("osdag.data.ResourceFiles.images").joinpath("1.RRFF.PNG"))
        elif val == 'Hinged':
            return str(files("osdag.data.ResourceFiles.images").joinpath("5.RRRF.PNG"))
        elif val == 'Roller':
            return str(files("osdag.data.ResourceFiles.images").joinpath("4.RRFR.PNG"))


    def fn_end2_image(self, *args):
        if len(args) == 1 and isinstance(args[0], list):
            args = args[0]
        end1 = args[0] if args else None
        end2 = args[1] if len(args) > 1 else None
        print("end 1 and end 2 are {}".format((end1, end2)))
        if end1 == 'Fixed':
            if end2 == 'Fixed':
                return str(files("osdag.data.ResourceFiles.images").joinpath("6.RRRR.PNG"))
            elif end2 == 'Free':
                return str(files("osdag.data.ResourceFiles.images").joinpath("1.RRFF_rotated.PNG"))
            elif end2 == 'Hinged':
                return str(files("osdag.data.ResourceFiles.images").joinpath("5.RRRF_rotated.PNG"))
            elif end2 == 'Roller':
                return str(files("osdag.data.ResourceFiles.images").joinpath("4.RRFR_rotated.PNG"))
        elif end1 == 'Free':
            return str(files("osdag.data.ResourceFiles.images").joinpath("1.RRFF.PNG"))
        elif end1 == 'Hinged':
            if end2 == 'Fixed':
                return str(files("osdag.data.ResourceFiles.images").joinpath("5.RRRF.PNG"))
            elif end2 == 'Hinged':
                return str(files("osdag.data.ResourceFiles.images").joinpath("3.RFRF.PNG"))
            elif end2 == 'Roller':
                return str(files("osdag.data.ResourceFiles.images").joinpath("2.FRFR_rotated.PNG"))
        elif end1 == 'Roller':
            if end2 == 'Fixed':
                return str(files("osdag.data.ResourceFiles.images").joinpath("4.RRFR.PNG"))
            elif end2 == 'Hinged':
                return str(files("osdag.data.ResourceFiles.images").joinpath("2.FRFR.PNG"))

    def input_value_changed(self, *args, **kwargs):
        lst = []
        # Section profile changes should update section designation (like in flexure.py)
        t1 = ([KEY_SEC_PROFILE], KEY_SECSIZE, TYPE_COMBOBOX_CUSTOMIZED, self.fn_section_designation)
        lst.append(t1)
        t2 = ([KEY_LYY], KEY_END_COND_YY, TYPE_COMBOBOX_CUSTOMIZED, self.get_end_conditions)
        lst.append(t2)
        t3 = ([KEY_LZZ], KEY_END_COND_ZZ, TYPE_COMBOBOX_CUSTOMIZED, self.get_end_conditions)
        lst.append(t3)
        t4 = ([KEY_MATERIAL], KEY_MATERIAL, TYPE_CUSTOM_MATERIAL, self.new_material)
        lst.append(t4)
        t5 = ([KEY_END1, KEY_END2], KEY_IMAGE, TYPE_IMAGE, self.fn_end2_image)
        lst.append(t5)
        t6 = ([KEY_END1_Y], KEY_END2_Y, TYPE_COMBOBOX, self.fn_end1_end2)
        lst.append(t6)
        t7 = ([KEY_END1_Y, KEY_END2_Y], KEY_IMAGE_Y, TYPE_IMAGE, self.fn_end2_image)
        lst.append(t7)
        # t8 = (KEY_END2, KEY_IMAGE, TYPE_IMAGE, self.fn_end2_image)
        # lst.append(t8)
        return lst

    def output_values(self, flag):
        # --- DEBUG: Print effective_length_yy at the start of output_values ---
        print("[DEBUG][output_values] self.effective_length_yy:", getattr(self, 'effective_length_yy', None))
        if not hasattr(self, 'effective_length_yy') or self.effective_length_yy is None:
            print("[WARNING][output_values] self.effective_length_yy is missing or None at output dock refresh!")
        def get_numeric(val):
            try:
                if val is None or val == '' or val in ['a', 'A']:
                    return None
                return float(val)
            except Exception:
                return None
        """
        Output the actual calculated values for effective length (YY) and slenderness ratio (YY), not classification text.
        """
        out_list = []
        def safe_display(val):
            try:
                if val is None:
                    return ''
                if isinstance(val, float):
                    return f"{val:.2f}"
                return str(val)
            except Exception:
                return str(val)

        # --- Always show Effective Lengths (YY/ZZ) at the top of output dock ---
        eff_len_yy = ''
        eff_len_zz = ''
        out_list.append((None, "Effective Length", TYPE_TITLE, None, True))
        # Forcefully show debug/calculation info for effective_length_yy, even if not used in output
        debug_yy_val = None
        if hasattr(self, 'effective_length_yy'):
            try:
                debug_yy_val = float(self.effective_length_yy) if self.effective_length_yy is not None else None
            except (TypeError, ValueError):
                debug_yy_val = None
        if debug_yy_val is not None:
            debug_yy = f"[DEBUG] Calculated effective_length_yy: {debug_yy_val}"
            out_list.append((None, debug_yy, TYPE_TITLE, None, True))
        if hasattr(self, 'effective_length_zz') and self.effective_length_zz is not None:
            try:
                vnum = float(self.effective_length_zz) if self.effective_length_zz is not None else None
                debug_zz = f"[DEBUG] Calculated effective_length_zz: {vnum}"
                out_list.append((None, debug_zz, TYPE_TITLE, None, True))
            except (TypeError, ValueError):
                pass
        if hasattr(self, 'result') and isinstance(self.result, dict):
            # Only use numeric values for effective length, skip any string like 'mpc400', 'mpc', etc.
            for k in ['effective_length_yy', 'Effective_length_yy', 'Effective Length YY']:
                v = self.result.get(k, None)
                try:
                    vnum = float(v) if v is not None else None
                    eff_len_yy = safe_display(vnum)
                    break
                except (TypeError, ValueError):
                    continue
            for k in ['effective_length_zz', 'Effective_length_zz', 'Effective Length ZZ']:
                v = self.result.get(k, None)
                try:
                    vnum = float(v) if v is not None else None
                    eff_len_zz = safe_display(vnum)
                    break
                except (TypeError, ValueError):
                    continue
        # Fallback to attribute if not found in result, only if numeric
        if not eff_len_yy and hasattr(self, 'effective_length_yy'):
            try:
                vnum = float(self.effective_length_yy) if self.effective_length_yy is not None else None
                eff_len_yy = safe_display(vnum)
            except (TypeError, ValueError):
                pass
        if not eff_len_zz and hasattr(self, 'effective_length_zz'):
            try:
                vnum = float(self.effective_length_zz) if self.effective_length_zz is not None else None
                eff_len_zz = safe_display(vnum)
            except (TypeError, ValueError):
                pass
        # Fallback to optimum_section_ur_results if still not found, only if numeric
        if (not eff_len_yy or not eff_len_zz) and hasattr(self, 'optimum_section_ur_results') and self.optimum_section_ur_results:
            best_ur = min(self.optimum_section_ur_results.keys())
            best_result = self.optimum_section_ur_results[best_ur]
            if not eff_len_yy:
                for k in ['Effective_length_yy', 'Effective Length YY', 'effective_length_yy']:
                    v = best_result.get(k, None)
                    try:
                        vnum = float(v) if v is not None else None
                        eff_len_yy = safe_display(vnum)
                        break
                    except (TypeError, ValueError):
                        continue
            if not eff_len_zz:
                for k in ['Effective_length_zz', 'Effective Length ZZ', 'effective_length_zz']:
                    v = best_result.get(k, None)
                    try:
                        vnum = float(v) if v is not None else None
                        eff_len_zz = safe_display(vnum)
                        break
                    except (TypeError, ValueError):
                        continue
        # --- Final fallback: if eff_len_yy is still blank, but self.effective_length_yy is set and numeric, use it ---
        if (not eff_len_yy or eff_len_yy == '') and hasattr(self, 'effective_length_yy'):
            try:
                vnum = float(self.effective_length_yy) if self.effective_length_yy is not None else None
                eff_len_yy = safe_display(vnum)
            except (TypeError, ValueError):
                pass
        if (not eff_len_zz or eff_len_zz == '') and hasattr(self, 'effective_length_zz'):
            try:
                vnum = float(self.effective_length_zz) if self.effective_length_zz is not None else None
                eff_len_zz = safe_display(vnum)
            except (TypeError, ValueError):
                pass
        # --- FORCE: Always show self.effective_length_yy as string in output dock for testing ---
        eff_len_yy_forced = ''
        if hasattr(self, 'effective_length_yy') and self.effective_length_yy is not None:
            try:
                eff_len_yy_forced = str(float(self.effective_length_yy))
            except Exception:
                eff_len_yy_forced = str(self.effective_length_yy)
        out_list.append((KEY_EFF_LEN_YY, "Effective Length (YY)", TYPE_TEXTBOX, eff_len_yy_forced, True))
        out_list.append((KEY_EFF_LEN_ZZ, "Effective Length (ZZ)", TYPE_TEXTBOX, eff_len_zz, True))

        # Slenderness Ratios
        out_list.append((None, "Slenderness Ratios", TYPE_TITLE, None, True))
        slender_yy = ''
        slender_zz = ''
        if flag:
            slender_yy_val = None
            slender_zz_val = None
            # 1. Try optimum_section_ur_results best result FIRST (most reliable)
            if hasattr(self, 'optimum_section_ur_results') and self.optimum_section_ur_results:
                best_ur = min(self.optimum_section_ur_results.keys())
                best_result = self.optimum_section_ur_results[best_ur]
                for k in ['Effective_sr_yy', 'Slenderness YY', 'effective_sr_yy', 'Slenderness_yy']:
                    if k in best_result:
                        try:
                            v = get_numeric(best_result[k])
                        except Exception:
                            v = None
                        if v is not None:
                            slender_yy_val = v
                            break
                for k in ['Effective_sr_zz', 'Slenderness ZZ', 'effective_sr_zz', 'Slenderness_zz']:
                    if k in best_result:
                        try:
                            v = get_numeric(best_result[k])
                        except Exception:
                            v = None
                        if v is not None:
                            slender_zz_val = v
                            break
            # 2. Fallback to direct attribute if not found above, with robust error handling
            if slender_yy_val is None and hasattr(self, 'effective_sr_yy'):
                try:
                    slender_yy_val = get_numeric(self.effective_sr_yy)
                except Exception:
                    slender_yy_val = None
            if slender_zz_val is None and hasattr(self, 'effective_sr_zz'):
                try:
                    slender_zz_val = get_numeric(self.effective_sr_zz)
                except Exception:
                    slender_zz_val = None
            slender_yy = safe_display(slender_yy_val) if slender_yy_val is not None else ''
            slender_zz = safe_display(slender_zz_val) if slender_zz_val is not None else ''
        out_list.append((KEY_SLENDER_YY, "Slenderness Ratio (YY)", TYPE_TEXTBOX, slender_yy, True))
        out_list.append((KEY_SLENDER_ZZ, "Slenderness Ratio (ZZ)", TYPE_TEXTBOX, slender_zz, True))
        
        # Design Values
        out_list.append((None, "Design Values", TYPE_TITLE, None, True))
        fcd = ''
        design_compressive = ''
        if flag:
            if hasattr(self, 'result_fcd') and self.result_fcd is not None:
                fcd = safe_display(self.result_fcd)
            elif hasattr(self, 'optimum_section_ur_results') and self.optimum_section_ur_results:
                best_ur = min(self.optimum_section_ur_results.keys()) if self.optimum_section_ur_results else None
                if best_ur:
                    fcd = safe_display(self.optimum_section_ur_results[best_ur].get('FCD', ''))
            if hasattr(self, 'result_capacity') and self.result_capacity is not None:
                design_compressive = safe_display(self.result_capacity)
            elif hasattr(self, 'optimum_section_ur_results') and self.optimum_section_ur_results:
                best_ur = min(self.optimum_section_ur_results.keys()) if self.optimum_section_ur_results else None
                if best_ur:
                    design_compressive = safe_display(self.optimum_section_ur_results[best_ur].get('Capacity', ''))
        out_list.append((KEY_FCD, "Design Compressive Stress (fcd)", TYPE_TEXTBOX, fcd, True))
        out_list.append((KEY_DESIGN_COMPRESSIVE, "Design Compressive Strength", TYPE_TEXTBOX, design_compressive, True))
        
        # Utilization Ratio
        out_list.append((None, "Utilization Ratio", TYPE_TITLE, None, True))
        ur_value = ''
        if flag:
            if hasattr(self, 'result_UR') and self.result_UR is not None:
                ur_value = safe_display(self.result_UR)
            elif hasattr(self, 'optimum_section_ur_results') and self.optimum_section_ur_results:
                best_ur = min(self.optimum_section_ur_results.keys()) if self.optimum_section_ur_results else None
                if best_ur:
                    ur_value = safe_display(best_ur)
        out_list.append(("utilization_ratio", "Utilization Ratio", TYPE_TEXTBOX, ur_value, True))
        
        # Section Classification (show as Plastic, Semi-Compact, etc.)
        out_list.append((None, "Section Classification", TYPE_TITLE, None, True))
        section_class = ''
        if flag:
            # Try self.result first
            if hasattr(self, 'result') and isinstance(self.result, dict):
                for k in ['section_class', 'Section class', 'Section_class', 'sectionClass']:
                    if k in self.result and self.result[k] not in [None, '', 'a', 'A']:
                        section_class = str(self.result[k])
                        break
            # Fallback to attribute
            if not section_class and hasattr(self, 'result_section_class') and self.result_section_class not in [None, '', 'a', 'A']:
                section_class = str(self.result_section_class)
            # Fallback to optimum_section_ur_results if still not found
            if not section_class and hasattr(self, 'optimum_section_ur_results') and self.optimum_section_ur_results:
                best_ur = min(self.optimum_section_ur_results.keys())
                best_result = self.optimum_section_ur_results[best_ur]
                for k in ['Section class', 'section_class', 'Section_class', 'sectionClass']:
                    if k in best_result and best_result[k] not in [None, '', 'a', 'A']:
                        section_class = str(best_result[k])
                        break
        out_list.append(("section_class", "Section Class", TYPE_TEXTBOX, section_class, True))
        
        # Effective Area
        out_list.append((None, "Effective Area", TYPE_TITLE, None, True))
        effective_area = ''
        if flag:
            if hasattr(self, 'result_effective_area') and self.result_effective_area is not None:
                effective_area = safe_display(self.result_effective_area)
            elif hasattr(self, 'optimum_section_ur_results') and self.optimum_section_ur_results:
                best_ur = min(self.optimum_section_ur_results.keys()) if self.optimum_section_ur_results else None
                if best_ur:
                    effective_area = safe_display(self.optimum_section_ur_results[best_ur].get('Effective area', ''))
        out_list.append(("effective_area", "Effective Area (mm²)", TYPE_TEXTBOX, effective_area, True))
        
        # Buckling Curve Classification
        out_list.append((None, "Buckling Curve Classification", TYPE_TITLE, None, True))
        bc_yy = ''
        bc_zz = ''
        if flag:
            # --- UI Patch: Always show the latest value from self.result for output dock fields ---
            if hasattr(self, 'result') and isinstance(self.result, dict):
                for k in ['buckling_curve_yy', 'Buckling_curve_yy', 'Buckling Curve YY']:
                    if k in self.result and self.result[k] not in [None, '', 'a', 'A']:
                        bc_yy = str(self.result[k])
                        break
                for k in ['buckling_curve_zz', 'Buckling_curve_zz', 'Buckling Curve ZZ']:
                    if k in self.result and self.result[k] not in [None, '', 'a', 'A']:
                        bc_zz = str(self.result[k])
                        break
            # Fallback to attribute if not found in result
            if not bc_yy and hasattr(self, 'result_bc_yy') and self.result_bc_yy not in [None, '', 'a', 'A']:
                bc_yy = str(self.result_bc_yy)
            if not bc_zz and hasattr(self, 'result_bc_zz') and self.result_bc_zz not in [None, '', 'a', 'A']:
                bc_zz = str(self.result_bc_zz)
            # Fallback to optimum_section_ur_results if still not found
            if (not bc_yy or not bc_zz) and hasattr(self, 'optimum_section_ur_results') and self.optimum_section_ur_results:
                best_ur = min(self.optimum_section_ur_results.keys())
                best_result = self.optimum_section_ur_results[best_ur]
                if not bc_yy:
                    for k in ['Buckling_curve_yy', 'Buckling Curve YY', 'buckling_curve_yy']:
                        if k in best_result and best_result[k] not in [None, '', 'a', 'A']:
                            bc_yy = str(best_result[k])
                            break
                if not bc_zz:
                    for k in ['Buckling_curve_zz', 'Buckling Curve ZZ', 'buckling_curve_zz']:
                        if k in best_result and best_result[k] not in [None, '', 'a', 'A']:
                            bc_zz = str(best_result[k])
                            break
            # If bc_zz is still 'A' (default), set to blank
            if bc_zz == 'A':
                bc_zz = ''
            out_list.append(("buckling_curve_yy", "Buckling Curve (YY)", TYPE_TEXTBOX, bc_yy, True))
            out_list.append(("buckling_curve_zz", "Buckling Curve (ZZ)", TYPE_TEXTBOX, bc_zz, True))
        
        # Imperfection Factor
        out_list.append((None, "Imperfection Factor", TYPE_TITLE, None, True))
        if_yy = ''
        if_zz = ''
        if flag:
            if hasattr(self, 'result_IF_yy') and self.result_IF_yy is not None:
                if_yy = safe_display(self.result_IF_yy)
            elif hasattr(self, 'optimum_section_ur_results') and self.optimum_section_ur_results:
                best_ur = min(self.optimum_section_ur_results.keys()) if self.optimum_section_ur_results else None
                if best_ur:
                    if_yy = safe_display(self.optimum_section_ur_results[best_ur].get('IF_yy', ''))
            if hasattr(self, 'result_IF_zz') and self.result_IF_zz is not None:
                if_zz = safe_display(self.result_IF_zz)
            elif hasattr(self, 'optimum_section_ur_results') and self.optimum_section_ur_results:
                best_ur = min(self.optimum_section_ur_results.keys()) if self.optimum_section_ur_results else None
                if best_ur:
                    if_zz = safe_display(self.optimum_section_ur_results[best_ur].get('IF_zz', ''))
        out_list.append(("imperfection_factor_yy", "Imperfection Factor (YY)", TYPE_TEXTBOX, if_yy, True))
        out_list.append(("imperfection_factor_zz", "Imperfection Factor (ZZ)", TYPE_TEXTBOX, if_zz, True))
        
        # Euler Buckling Stress
        out_list.append((None, "Euler Buckling Stress", TYPE_TITLE, None, True))
        ebs_yy = ''
        ebs_zz = ''
        if flag:
            if hasattr(self, 'result_ebs_yy') and self.result_ebs_yy is not None:
                ebs_yy = safe_display(self.result_ebs_yy)
            elif hasattr(self, 'optimum_section_ur_results') and self.optimum_section_ur_results:
                best_ur = min(self.optimum_section_ur_results.keys()) if self.optimum_section_ur_results else None
                if best_ur:
                    ebs_yy = safe_display(self.optimum_section_ur_results[best_ur].get('EBS_yy', ''))
            if hasattr(self, 'result_ebs_zz') and self.result_ebs_zz is not None:
                ebs_zz = safe_display(self.result_ebs_zz)
            elif hasattr(self, 'optimum_section_ur_results') and self.optimum_section_ur_results:
                best_ur = min(self.optimum_section_ur_results.keys()) if self.optimum_section_ur_results else None
                if best_ur:
                    ebs_zz = safe_display(self.optimum_section_ur_results[best_ur].get('EBS_zz', ''))
        out_list.append(("euler_buckling_stress_yy", "Euler Buckling Stress (YY)", TYPE_TEXTBOX, ebs_yy, True))
        out_list.append(("euler_buckling_stress_zz", "Euler Buckling Stress (ZZ)", TYPE_TEXTBOX, ebs_zz, True))
        
        # Non-dimensional Effective Slenderness Ratio
        out_list.append((None, "Non-dimensional Effective Slenderness Ratio", TYPE_TITLE, None, True))
        nd_esr_yy = ''
        nd_esr_zz = ''
        if flag:
            # --- UI Patch: Always show the latest value from self.result for output dock fields ---
            if hasattr(self, 'result') and isinstance(self.result, dict):
                for k in ['nd_esr_yy', 'ND_ESR_yy', 'ND ESR YY']:
                    if k in self.result and self.result[k] not in [None, '', 'a', 'A']:
                        nd_esr_yy = safe_display(self.result[k])
                        break
                for k in ['nd_esr_zz', 'ND_ESR_zz', 'ND ESR ZZ']:
                    if k in self.result and self.result[k] not in [None, '', 'a', 'A']:
                        nd_esr_zz = safe_display(self.result[k])
                        break
            # Fallback to attribute if not found in result
            if not nd_esr_yy and hasattr(self, 'result_nd_esr_yy') and self.result_nd_esr_yy not in [None, '', 'a', 'A']:
                nd_esr_yy = safe_display(self.result_nd_esr_yy)
            if not nd_esr_zz and hasattr(self, 'result_nd_esr_zz') and self.result_nd_esr_zz not in [None, '', 'a', 'A']:
                nd_esr_zz = safe_display(self.result_nd_esr_zz)
            # Fallback to optimum_section_ur_results if still not found
            if (not nd_esr_yy or not nd_esr_zz) and hasattr(self, 'optimum_section_ur_results') and self.optimum_section_ur_results:
                best_ur = min(self.optimum_section_ur_results.keys())
                best_result = self.optimum_section_ur_results[best_ur]
                if not nd_esr_yy:
                    for k in ['ND_ESR_yy', 'nd_esr_yy', 'ND ESR YY']:
                        if k in best_result and best_result[k] not in [None, '', 'a', 'A']:
                            nd_esr_yy = safe_display(best_result[k])
                            break
                if not nd_esr_zz:
                    for k in ['ND_ESR_zz', 'nd_esr_zz', 'ND ESR ZZ']:
                        if k in best_result and best_result[k] not in [None, '', 'a', 'A']:
                            nd_esr_zz = safe_display(best_result[k])
                            break
            out_list.append(("nd_esr_yy", "ND ESR (YY)", TYPE_TEXTBOX, nd_esr_yy, True))
            out_list.append(("nd_esr_zz", "ND ESR (ZZ)", TYPE_TEXTBOX, nd_esr_zz, True))
        
        # Phi Values
        out_list.append((None, "Phi Values", TYPE_TITLE, None, True))
        phi_yy = ''
        phi_zz = ''
        if flag:
            if hasattr(self, 'result_phi_yy') and self.result_phi_yy is not None:
                phi_yy = safe_display(self.result_phi_yy)
            elif hasattr(self, 'optimum_section_ur_results') and self.optimum_section_ur_results:
                best_ur = min(self.optimum_section_ur_results.keys()) if self.optimum_section_ur_results else None
                if best_ur:
                    phi_yy = safe_display(self.optimum_section_ur_results[best_ur].get('phi_yy', ''))
            if hasattr(self, 'result_phi_zz') and self.result_phi_zz is not None:
                phi_zz = safe_display(self.result_phi_zz)
            elif hasattr(self, 'optimum_section_ur_results') and self.optimum_section_ur_results:
                best_ur = min(self.optimum_section_ur_results.keys()) if self.optimum_section_ur_results else None
                if best_ur:
                    phi_zz = safe_display(self.optimum_section_ur_results[best_ur].get('phi_zz', ''))
        out_list.append(("phi_yy", "Phi (YY)", TYPE_TEXTBOX, phi_yy, True))
        out_list.append(("phi_zz", "Phi (ZZ)", TYPE_TEXTBOX, phi_zz, True))
        
        # Stress Reduction Factor
        out_list.append((None, "Stress Reduction Factor", TYPE_TITLE, None, True))
        srf_yy = ''
        srf_zz = ''
        if flag:
            if hasattr(self, 'result_srf_yy') and self.result_srf_yy is not None:
                srf_yy = safe_display(self.result_srf_yy)
            elif hasattr(self, 'optimum_section_ur_results') and self.optimum_section_ur_results:
                best_ur = min(self.optimum_section_ur_results.keys()) if self.optimum_section_ur_results else None
                if best_ur:
                    srf_yy = safe_display(self.optimum_section_ur_results[best_ur].get('SRF_yy', ''))
            if hasattr(self, 'result_srf_zz') and self.result_srf_zz is not None:
                srf_zz = safe_display(self.result_srf_zz)
            elif hasattr(self, 'optimum_section_ur_results') and self.optimum_section_ur_results:
                best_ur = min(self.optimum_section_ur_results.keys()) if self.optimum_section_ur_results else None
                if best_ur:
                    srf_zz = safe_display(self.optimum_section_ur_results[best_ur].get('SRF_zz', ''))
        out_list.append(("stress_reduction_factor_yy", "SRF (YY)", TYPE_TEXTBOX, srf_yy, True))
        out_list.append(("stress_reduction_factor_zz", "SRF (ZZ)", TYPE_TEXTBOX, srf_zz, True))
        
        # Design Compressive Stress Values
        out_list.append((None, "Design Compressive Stress Values", TYPE_TITLE, None, True))
        fcd_1_yy = ''
        fcd_1_zz = ''
        fcd_2 = ''
        if flag:
            if hasattr(self, 'result_fcd_1_yy') and self.result_fcd_1_yy is not None:
                fcd_1_yy = safe_display(self.result_fcd_1_yy)
            elif hasattr(self, 'optimum_section_ur_results') and self.optimum_section_ur_results:
                best_ur = min(self.optimum_section_ur_results.keys()) if self.optimum_section_ur_results else None
                if best_ur:
                    fcd_1_yy = safe_display(self.optimum_section_ur_results[best_ur].get('FCD_1_yy', ''))
            if hasattr(self, 'result_fcd_1_zz') and self.result_fcd_1_zz is not None:
                fcd_1_zz = safe_display(self.result_fcd_1_zz)
            elif hasattr(self, 'optimum_section_ur_results') and self.optimum_section_ur_results:
                best_ur = min(self.optimum_section_ur_results.keys()) if self.optimum_section_ur_results else None
                if best_ur:
                    fcd_1_zz = safe_display(self.optimum_section_ur_results[best_ur].get('FCD_1_zz', ''))
            if hasattr(self, 'result_fcd_2') and self.result_fcd_2 is not None:
                fcd_2 = safe_display(self.result_fcd_2)
            elif hasattr(self, 'optimum_section_ur_results') and self.optimum_section_ur_results:
                best_ur = min(self.optimum_section_ur_results.keys()) if self.optimum_section_ur_results else None
                if best_ur:
                    fcd_2 = safe_display(self.optimum_section_ur_results[best_ur].get('FCD_2', ''))
        out_list.append(("fcd_1_yy", "FCD_1 (YY)", TYPE_TEXTBOX, fcd_1_yy, True))
        out_list.append(("fcd_1_zz", "FCD_1 (ZZ)", TYPE_TEXTBOX, fcd_1_zz, True))
        out_list.append(("fcd_2", "FCD_2", TYPE_TEXTBOX, fcd_2, True))
        
        # --- Channel and Lacing Details Section ---
        out_list.append((None, "Channel and Lacing Details", TYPE_TITLE, None, True))
        spacing_channels = ''
        if flag:
            if hasattr(self, 'result') and self.result.get('channel_spacing') is not None:
                spacing_channels = safe_display(self.result.get('channel_spacing'))
            elif hasattr(self, 'optimum_section_ur_results') and self.optimum_section_ur_results:
                best_ur = min(self.optimum_section_ur_results.keys()) if self.optimum_section_ur_results else None
                if best_ur:
                    spacing_channels = safe_display(self.optimum_section_ur_results[best_ur].get('channel_spacing', ''))
        out_list.append(("channel_spacing", "Spacing Between Channels (mm)", TYPE_TEXTBOX, spacing_channels, True))

        # --- Tie Plate Section ---
        out_list.append((None, "Tie Plate", TYPE_TITLE, None, True))
        tie_plate_d = ''
        tie_plate_t = ''
        tie_plate_l = ''
        if flag:
            if hasattr(self, 'result') and self.result.get('tie_plate_d') is not None:
                tie_plate_d = safe_display(self.result.get('tie_plate_d'))
            elif hasattr(self, 'optimum_section_ur_results') and self.optimum_section_ur_results:
                best_ur = min(self.optimum_section_ur_results.keys()) if self.optimum_section_ur_results else None
                if best_ur:
                    tie_plate_d = safe_display(self.optimum_section_ur_results[best_ur].get('tie_plate_d', ''))
            if hasattr(self, 'result') and self.result.get('tie_plate_t') is not None:
                tie_plate_t = safe_display(self.result.get('tie_plate_t'))
            elif hasattr(self, 'optimum_section_ur_results') and self.optimum_section_ur_results:
                best_ur = min(self.optimum_section_ur_results.keys()) if self.optimum_section_ur_results else None
                if best_ur:
                    tie_plate_t = safe_display(self.optimum_section_ur_results[best_ur].get('tie_plate_t', ''))
            if hasattr(self, 'result') and self.result.get('tie_plate_l') is not None:
                tie_plate_l = safe_display(self.result.get('tie_plate_l'))
            elif hasattr(self, 'optimum_section_ur_results') and self.optimum_section_ur_results:
                best_ur = min(self.optimum_section_ur_results.keys()) if self.optimum_section_ur_results else None
                if best_ur:
                    tie_plate_l = safe_display(self.optimum_section_ur_results[best_ur].get('tie_plate_l', ''))
        out_list.append(("tie_plate_d", "Tie Plate Depth D (mm)", TYPE_TEXTBOX, tie_plate_d, True))
        out_list.append(("tie_plate_t", "Tie Plate Thickness t (mm)", TYPE_TEXTBOX, tie_plate_t, True))
        out_list.append(("tie_plate_l", "Tie Plate Length L (mm)", TYPE_TEXTBOX, tie_plate_l, True))

        # --- Lacing Spacing Section ---
        out_list.append((None, "Lacing Spacing", TYPE_TITLE, None, True))
        lacing_spacing = ''
        if flag:
            if hasattr(self, 'result') and self.result.get('lacing_spacing') is not None:
                lacing_spacing = safe_display(self.result.get('lacing_spacing'))
            elif hasattr(self, 'optimum_section_ur_results') and self.optimum_section_ur_results:
                best_ur = min(self.optimum_section_ur_results.keys()) if self.optimum_section_ur_results else None
                if best_ur:
                    lacing_spacing = safe_display(self.optimum_section_ur_results[best_ur].get('lacing_spacing', ''))
        out_list.append(("lacing_spacing", "Lacing Spacing (L0) (mm)", TYPE_TEXTBOX, lacing_spacing, True))

        return out_list
    '''
    def func_for_validation(self, design_dictionary):

        all_errors = []
        self.design_status = False
        flag = False
        option_list = self.input_values()
        missing_fields_list = []
        # Only check truly required fields; allow optional fields to be missing
        for option in option_list:
            key = option[0]
            label = option[1]
            field_type = option[2]
            value = design_dictionary.get(key, None)
            # Only block if a critical field is missing
            if field_type == TYPE_TEXTBOX and key in [KEY_SECSIZE, KEY_SEC_MATERIAL, KEY_UNSUPPORTED_LEN_ZZ, KEY_UNSUPPORTED_LEN_YY, KEY_AXIAL]:
                if value in [None, '', [], 'Select', 'Select Section', 'Select Material']:
                    missing_fields_list.append(label)
            # For other fields, just warn and skip related calculations
        # Additional required field checks
        sec_list = design_dictionary.get(KEY_SECSIZE, [])
        # Only add to missing_fields_list if sec_list is empty or only contains 'Select Section'
        if not sec_list or (isinstance(sec_list, list) and all(s in ['', 'Select Section'] for s in sec_list)):
            missing_fields_list.append('Section Size')
        material = design_dictionary.get(KEY_SEC_MATERIAL, '')
        if not material or material in ['', 'Select Material']:
            missing_fields_list.append('Material')
        len_zz = design_dictionary.get(KEY_UNSUPPORTED_LEN_ZZ, None)
        len_yy = design_dictionary.get(KEY_UNSUPPORTED_LEN_YY, None)
        try:
            if float(len_zz) <= 0:
                missing_fields_list.append('Actual Length (z-z), mm')
        except:
            missing_fields_list.append('Actual Length (z-z), mm')
        try:
            if float(len_yy) <= 0:
                missing_fields_list.append('Actual Length (y-y), mm')
        except:
            missing_fields_list.append('Actual Length (y-y), mm')
        axial = design_dictionary.get(KEY_AXIAL, None)
        try:
            if float(axial) <= 0:
                missing_fields_list.append('Axial Load (kN)')
        except:
            missing_fields_list.append('Axial Load (kN)')
        if len(missing_fields_list) > 0:
            error = self.generate_missing_fields_error_string(missing_fields_list)
            all_errors.append(error)
            self.logger.error(f"Missing/invalid input fields: {', '.join(missing_fields_list)}")
            return all_errors
        else:
            flag = True
        if flag:

            self.set_input_values(design_dictionary)
            if self.design_status == False and self.failed_design_dict is not None and len(self.failed_design_dict) > 0:
                self.logger.error(
                    "Design Failed, Check Design Report"
                )
                return # ['Design Failed, Check Design Report'] @TODO
            elif self.design_status:
                pass
        else:
            return all_errors
    '''
    def get_3d_components(self, *args, **kwargs):
        components = []
        t1 = ('Model', self.call_3DModel)
        components.append(t1)
        # t3 = ('Column', self.call_3DColumn)
        # components.append(t3)
        return components

    # warn if a beam of older version of IS 808 is selected
    def warn_text(self):
        """ give logger warning when a beam from the older version of IS 808 is selected """
        global logger
        red_list = red_list_function()

        if (self.sec_profile == VALUES_SEC_PROFILE[0]):  # Beams and Columns
            for section in self.sec_list:
                if section in red_list:
                    logger.warning(" : You are using a section ({}) (in red color) that is not available in latest version of IS 808".format(section))

    # Setting inputs from the input dock GUI
    def set_input_values(self, design_dictionary):
        # self.logger.info(f"set_input_values called with: {design_dictionary}")
        super(Member, self).set_input_values(design_dictionary)
        # section properties
        self.module = design_dictionary.get(KEY_DISP_LACEDCOL, "")
        self.mainmodule = 'Columns with known support conditions'
        self.sec_profile = design_dictionary.get(KEY_LACEDCOL_SEC_PROFILE, "")
        self.sec_list = design_dictionary.get(KEY_SECSIZE, [])
        # Coerce sec_list to a list if it's a string
        if isinstance(self.sec_list, str):
            if self.sec_list and self.sec_list != 'Select Section':
                self.sec_list = [self.sec_list]
            else:
                self.sec_list = []
        elif not isinstance(self.sec_list, list):
            self.sec_list = list(self.sec_list) if self.sec_list else []
        self.material = design_dictionary.get(KEY_SEC_MATERIAL, "")
        # Defensive checks for required fields
        def is_valid_material(mat):
            if isinstance(mat, list):
                return any(m and m != 'Select Material' for m in mat)
            return mat and mat != 'Select Material'
        if not is_valid_material(self.material):
            self.logger.error("Material is missing or invalid.")
            self.design_status = False
            return
        def is_valid_section(sec):
            if isinstance(sec, list):
                return any(s and s != 'Select Section' for s in sec)
            return sec and sec != 'Select Section'
        if not is_valid_section(self.sec_list):
            self.logger.error(f"Section list is missing or invalid: {self.sec_list}")
            self.design_status = False
            return
        # section user data
        try:
            self.length_zz = float(design_dictionary.get(KEY_UNSUPPORTED_LEN_ZZ, 0))
            if self.length_zz <= 0:
                raise ValueError
        except:
            self.logger.error("Actual Length (z-z), mm is missing or invalid.")
            self.design_status = False
            return
        try:
            self.length_yy = float(design_dictionary.get(KEY_UNSUPPORTED_LEN_YY, 0))
            if self.length_yy <= 0:
                raise ValueError
        except:
            self.logger.error("Actual Length (y-y), mm is missing or invalid.")
            self.design_status = False
            return
        # end condition
        self.end_1_z = design_dictionary.get(KEY_END1, "")
        self.end_2_z = design_dictionary.get(KEY_END2, "")
        self.end_1_y = design_dictionary.get(KEY_END1_Y, "")
        self.end_2_y = design_dictionary.get(KEY_END2_Y, "")
        # factored loads
        try:
            axial_force = float(design_dictionary.get(KEY_AXIAL, 0))
            if axial_force <= 0:
                raise ValueError
        except:
            self.logger.error("Axial Load (kN) is missing or invalid.")
            self.design_status = False
            return
        self.load = Load(axial_force=axial_force, shear_force=0.0, moment=0.0, moment_minor=0.0, unit_kNm=True)
        # design preferences
        try:
            self.allowable_utilization_ratio = float(design_dictionary.get(KEY_ALLOW_UR, 1.0))
        except:
            self.allowable_utilization_ratio = 1.0
        try:
            self.effective_area_factor = float(design_dictionary.get(KEY_EFFECTIVE_AREA_PARA, 1.0))
        except:
            self.effective_area_factor = 1.0
        try:
            self.optimization_parameter = design_dictionary[KEY_OPTIMIZATION_PARA]
        except:
            self.optimization_parameter = 'Utilization Ratio'
        try:
            self.steel_cost_per_kg = float(design_dictionary[KEY_STEEL_COST])
        except:
            self.steel_cost_per_kg = 50
        self.allowed_sections = ['Plastic', 'Compact', 'Semi-Compact', 'Slender']

        # Defensive: Only run if section list and material are valid
        if self.sec_list and self.material:
            # Clear material cache when material changes to ensure fresh properties
            self.material_lookup_cache = {}
            
            # Initialize material_property BEFORE section_classification
            self.material_property = Material(material_grade=self.material, thickness=0)
            self.flag = self.section_classification()
            if self.flag:
                self.design_column()
                self.results()
        
        # safety factors
        self.gamma_m0 = IS800_2007.cl_5_4_1_Table_5["gamma_m0"]["yielding"]
        
        # initialize the design status
        self.design_status_list = []
        self.design_status = False
        self.failed_design_dict = {}
        # Always perform calculations if required fields are present

    def store_additional_outputs(self, d=None, t=None, l=None, spacing=None, c_spacing=None, ur=None):
        """
        Store additional calculated outputs for tie plate, lacing, and channel spacing in self.result and, if ur is provided, in self.optimum_section_ur_results[ur].
        """
        if d is not None:
            self.result['tie_plate_d'] = d
        if t is not None:
            self.result['tie_plate_t'] = t
        if l is not None:
            self.result['tie_plate_l'] = l
        if spacing is not None:
            self.result['lacing_spacing'] = spacing
        if c_spacing is not None:
            self.result['channel_spacing'] = c_spacing
        # Also store in optimum_section_ur_results[ur] if ur is provided
        if ur is not None and hasattr(self, 'optimum_section_ur_results') and ur in self.optimum_section_ur_results:
            if d is not None:
                self.optimum_section_ur_results[ur]['tie_plate_d'] = d
            if t is not None:
                self.optimum_section_ur_results[ur]['tie_plate_t'] = t
            if l is not None:
                self.optimum_section_ur_results[ur]['tie_plate_l'] = l
            if spacing is not None:
                self.optimum_section_ur_results[ur]['lacing_spacing'] = spacing
            if c_spacing is not None:
                self.optimum_section_ur_results[ur]['channel_spacing'] = c_spacing
                
    def results(self):
        # Prevent duplicate logs in a single calculation
        if not hasattr(self, 'design_status_list') or self.design_status_list is None or not isinstance(self.design_status_list, list):
            self.design_status_list = []
        if hasattr(self, '_already_logged_failure'):
            del self._already_logged_failure

        if not self.optimum_section_ur:
            error_msg = "No sections available for design. Please check your input or section list."
            self.logger.error(error_msg)
            self.failed_reason = error_msg
            self.design_status = False
            self.failed_design_dict = {}
            return

        if len(self.optimum_section_ur) == 0:  # no design was successful
            if not hasattr(self, '_already_logged_failure'):
                self._already_logged_failure = True
                error_msg = "The sections selected by the solver from the defined list of sections did not satisfy the Utilization Ratio (UR) criteria"
                self.failed_reason = error_msg
            self.design_status = False
            if self.failed_design_dict is None or not isinstance(self.failed_design_dict, dict):
                self.failed_design_dict = {}
            if self.failed_design_dict and isinstance(self.failed_design_dict, dict) and len(self.failed_design_dict) > 0:
                self.logger.info("The details for the best section provided is being shown")
                self.result_UR = self.failed_design_dict.get('UR', None)
                self.common_result(
                    list_result=self.failed_design_dict,
                    result_type=None,
                )
                self.logger.warning("Re-define the list of sections or check the Design Preferences option and re-design.")
                return
            self.failed_design_dict = {}  # Always a dict for downstream code
            return

        _ = [i for i in self.optimum_section_ur if i > 1.0]

        if len(_)==1:
            temp = _[0]
        elif len(_)==0:
            temp = None
        else:
            temp = sorted(_)[0]
        self.failed_design_dict = self.optimum_section_ur_results[temp] if temp is not None else None

        # results based on UR
        if self.optimization_parameter == 'Utilization Ratio':
            # Debug logging
            # self.logger.info(f"Before filtering: optimum_section_ur = {self.optimum_section_ur}")
            # self.logger.info(f"allowable_utilization_ratio = {self.allowable_utilization_ratio}")
            
            filter_UR = filter(lambda x: x <= min(self.allowable_utilization_ratio, 1.0), self.optimum_section_ur)
            self.optimum_section_ur = list(filter_UR)
            
            # self.logger.info(f"After filtering: optimum_section_ur = {self.optimum_section_ur}")

            self.optimum_section_ur.sort()

            # selecting the section with most optimum UR
            if len(self.optimum_section_ur) == 0:  # no design was successful
                error_msg = f"The sections selected by the solver from the defined list of sections did not satisfy the Utilization Ratio (UR) criteria. Allowable UR: {self.allowable_utilization_ratio}"
                self.failed_reason = error_msg
                self.design_status = False
                
                # Fallback: If we have results but they were filtered out, show the best one anyway
                if hasattr(self, 'optimum_section_ur_results') and self.optimum_section_ur_results:
                    self.logger.info("Showing best available result despite UR filter failure")
                    best_ur = min(self.optimum_section_ur_results.keys())
                    self.result_UR = best_ur
                    self.common_result(
                        list_result=self.optimum_section_ur_results,
                        result_type=best_ur,
                    )
                    return
                
                if self.failed_design_dict and isinstance(self.failed_design_dict, dict) and len(self.failed_design_dict) > 0:
                    self.logger.info(
                    "The details for the best section provided is being shown"
                )
                    self.result_UR = self.failed_design_dict.get('UR', None) #temp  
                    self.common_result(
                        list_result=self.failed_design_dict,
                        result_type=None,
                    )
                    self.logger.warning(
                    "Re-define the list of sections or check the Design Preferences option and re-design."
                )
                    return

            self.failed_design_dict = {}
            self.result_UR = self.optimum_section_ur[-1]  # optimum section which passes the UR check

            self.design_status = True
            if self.result_UR in self.optimum_section_ur_results:
                self.common_result(
                    list_result=self.optimum_section_ur_results,
                    result_type=self.result_UR,
                )
            else:
                error_msg = f"Result UR {self.result_UR} not found in optimum_section_ur_results. No valid design result to display."
                self.logger.error(error_msg)
                self.failed_reason = error_msg
                self.design_status = False
        else:  # results based on cost
            self.optimum_section_cost.sort()

            # selecting the section with most optimum cost
            self.result_cost = self.optimum_section_cost[0]
            self.design_status = True

        for status in self.design_status_list:
            if status is False:
                self.design_status = False
                break
            else:
                self.design_status = True

    def common_result(self, list_result, result_type):
        # Defensive: handle None or wrong type for list_result
        if not isinstance(list_result, dict) or not list_result:
            self.logger.error("No valid results to display. Calculation did not yield any results.")
            # Set all result attributes to None or a safe default
            self.result_designation = None
            self.section_class = None
            self.result_section_class = None
            self.result_effective_area = None
            self.result_bc_zz = None
            self.result_bc_yy = None
            self.result_IF_zz = None
            self.result_IF_yy = None
            self.result_eff_len_zz = None
            self.result_eff_len_yy = None
            self.result_eff_sr_zz = None
            self.result_eff_sr_yy = None
            self.result_ebs_zz = None
            self.result_ebs_yy = None
            self.result_nd_esr_zz = None
            self.result_nd_esr_yy = None
            self.result_phi_zz = None
            self.result_phi_yy = None
            self.result_srf_zz = None
            self.result_srf_yy = None
            self.result_fcd_1_zz = None
            self.result_fcd_1_yy = None
            self.result_fcd_2 = None
            self.result_fcd_zz = None
            self.result_fcd_yy = None
            self.result_fcd = None
            self.result_capacity = None
            self.result_cost = None
            return

        # Defensive: handle None or missing result_type
        if result_type is None:
            # Try to get the first key if possible
            if list_result:
                result_type = next(iter(list_result.keys()))
            else:
                self.logger.error("No result type found in results.")
                return

        # Defensive: check if result_type exists in list_result
        if result_type not in list_result:
            self.logger.error(f"Result type '{result_type}' not found in results.")
            return

        # Now safe to access
        try:
            self.result_designation = list_result[result_type].get('Designation', None)
            self.section_class = self.input_section_classification.get(self.result_designation, [None])[0]

            if self.section_class == 'Slender':
                self.logger.warning(f"The trial section ({self.result_designation}) is Slender. Computing the Effective Sectional Area as per Sec. 9.7.2, Fig. 2 (B & C) of The National Building Code of India (NBC), 2016.")
            if getattr(self, 'effective_area_factor', 1.0) < 1.0:
                self.effective_area = round(self.effective_area * self.effective_area_factor, 2)
                # self.logger.warning("Reducing the effective sectional area as per the definition in the Design Preferences tab.")
                self.logger.info(f"The actual effective area is {round((self.effective_area / self.effective_area_factor), 2)} mm2 and the reduced effective area is {self.effective_area} mm2 [Reference: Cl. 7.3.2, IS 800:2007]")
            else:
                if self.result_designation in self.input_section_classification:
                    def safe_round(value, decimals=2):
                        if value is None:
                            return None
                        try:
                            return round(float(value), decimals)
                        except (ValueError, TypeError):
                            return None
                
                classification = self.input_section_classification[self.result_designation]
                flange_value = safe_round(classification[3] if len(classification) > 3 else None)
                web_value = safe_round(classification[4] if len(classification) > 4 else None)
                
                self.logger.info(
                    "The section is {}. The {} section  has  {} flange({}) and  {} web({}).  [Reference: Cl 3.7, IS 800:2007].".format(
                        classification[0] if len(classification) > 0 else 'Unknown',
                        self.result_designation,
                        classification[1] if len(classification) > 1 else 'Unknown', flange_value,
                        classification[2] if len(classification) > 2 else 'Unknown', web_value
                    ))

            self.result_section_class = list_result[result_type].get('Section class', None)
            self.result_effective_area = list_result[result_type].get('Effective area', None)
            self.result_bc_zz = list_result[result_type].get('Buckling_curve_zz', None)
            self.result_bc_yy = list_result[result_type].get('Buckling_curve_yy', None)
            self.result_IF_zz = list_result[result_type].get('IF_zz', None)
            self.result_IF_yy = list_result[result_type].get('IF_yy', None)
            self.result_eff_len_zz = list_result[result_type].get('Effective_length_zz', None)
            self.result_eff_len_yy = list_result[result_type].get('Effective_length_yy', None)
            self.result_eff_sr_zz = list_result[result_type].get('Effective_SR_zz', None)
            self.result_eff_sr_yy = list_result[result_type].get('Effective_SR_yy', None)
            self.result_ebs_zz = list_result[result_type].get('EBS_zz', None)
            self.result_ebs_yy = list_result[result_type].get('EBS_yy', None)
            self.result_nd_esr_zz = list_result[result_type].get('ND_ESR_zz', None)
            self.result_nd_esr_yy = list_result[result_type].get('ND_ESR_yy', None)
            self.result_phi_zz = list_result[result_type].get('phi_zz', None)
            self.result_phi_yy = list_result[result_type].get('phi_yy', None)
            self.result_srf_zz = list_result[result_type].get('SRF_zz', None)
            self.result_srf_yy = list_result[result_type].get('SRF_yy', None)
            self.result_fcd_1_zz = list_result[result_type].get('FCD_1_zz', None)
            self.result_fcd_1_yy = list_result[result_type].get('FCD_1_yy', None)
            self.result_fcd_2 = list_result[result_type].get('FCD_2', None)
            self.result_fcd_zz = list_result[result_type].get('FCD_zz', None)
            self.result_fcd_yy = list_result[result_type].get('FCD_yy', None)
            self.result_fcd = list_result[result_type].get('FCD', None)
            self.result_capacity = list_result[result_type].get('Capacity', None)
            self.result_cost = list_result[result_type].get('Cost', None)
        except Exception as e:
            # self.logger.error(f"Error extracting results: {e}")
            # Set all result attributes to None or a safe default
            self.result_designation = None
            self.section_class = None
            self.result_section_class = None
            self.result_effective_area = None
            self.result_bc_zz = None
            self.result_bc_yy = None
            self.result_IF_zz = None
            self.result_IF_yy = None
            self.result_eff_len_zz = None
            self.result_eff_len_yy = None
            self.result_eff_sr_zz = None
            self.result_eff_sr_yy = None
            self.result_ebs_zz = None
            self.result_ebs_yy = None
            self.result_nd_esr_zz = None
            self.result_nd_esr_yy = None
            self.result_phi_zz = None
            self.result_phi_yy = None
            self.result_srf_zz = None
            self.result_srf_yy = None
            self.result_fcd_1_zz = None
            self.result_fcd_1_yy = None
            self.result_fcd_2 = None
            self.result_fcd_zz = None
            self.result_fcd_yy = None
            self.result_fcd = None

    def save_design(self, popup_summary):
        # Safe rounding function for all round operations
        def safe_round(value, decimals=2):
            if value is None:
                return None
            try:
                return round(float(value), decimals)
            except (ValueError, TypeError):
                return None
        
        # Safe access to classification values
        def safe_classification_value(designation, index, default=None):
            if (designation in self.input_section_classification and 
                isinstance(self.input_section_classification[designation], (list, tuple)) and 
                len(self.input_section_classification[designation]) > index):
                return self.input_section_classification[designation][index]
            return default

        if self.design_status:
            if (self.design_status and self.failed_design_dict is None) or (not self.design_status and self.failed_design_dict is not None and hasattr(self.failed_design_dict, '__len__') and len(self.failed_design_dict) > 0):
                if self.sec_profile=='Columns' or self.sec_profile=='Beams' or self.sec_profile == VALUES_SEC_PROFILE[0]:
                    try:
                        result = Beam(designation=self.result_designation, material_grade=self.material)
                    except:
                        result = Column(designation=self.result_designation, material_grade=self.material)
                    self.section_property = result
                    self.report_column = {KEY_DISP_SEC_PROFILE: "ISection",
                                        KEY_DISP_SECSIZE: (self.section_property.designation, self.sec_profile),
                                        KEY_DISP_COLSEC_REPORT: self.section_property.designation,
                                        KEY_DISP_MATERIAL: self.section_property.material,
            #                                 KEY_DISP_APPLIED_AXIAL_FORCE: self.section_property.,
                                        KEY_REPORT_MASS: self.section_property.mass,
                                        KEY_REPORT_AREA: safe_round(self.section_property.area * 1e-2, 2),
                                        KEY_REPORT_DEPTH: self.section_property.depth,
                                        KEY_REPORT_WIDTH: self.section_property.flange_width,
                                        KEY_REPORT_WEB_THK: self.section_property.web_thickness,
                                        KEY_REPORT_FLANGE_THK: self.section_property.flange_thickness,
                                        KEY_DISP_FLANGE_S_REPORT: self.section_property.flange_slope,
                                        KEY_REPORT_R1: self.section_property.root_radius,
                                        KEY_REPORT_R2: self.section_property.toe_radius,
                                        KEY_REPORT_IZ: round(self.section_property.mom_inertia_z * 1e-4, 2),
                                        KEY_REPORT_IY: round(self.section_property.mom_inertia_y * 1e-4, 2),
                                        KEY_REPORT_RZ: round(self.section_property.rad_of_gy_z * 1e-1, 2),
                                        KEY_REPORT_RY: round(self.section_property.rad_of_gy_y * 1e-1, 2),
                                        KEY_REPORT_ZEZ: round(self.section_property.elast_sec_mod_z * 1e-3, 2),
                                        KEY_REPORT_ZEY: round(self.section_property.elast_sec_mod_y * 1e-3, 2),
                                        KEY_REPORT_ZPZ: round(self.section_property.plast_sec_mod_z * 1e-3, 2),
                                        KEY_REPORT_ZPY: round(self.section_property.plast_sec_mod_y * 1e-3, 2)}
                else:
                    #Update for section profiles RHS and SHS, CHS by making suitable elif condition.
                    self.report_column = {KEY_DISP_COLSEC_REPORT: getattr(self.section_property, 'designation', None),
                                        KEY_DISP_MATERIAL: getattr(self.section_property, 'material', ''),
                                        #                                 KEY_DISP_APPLIED_AXIAL_FORCE: getattr(self.section_property, 'applied_axial_force', ''),
                                        KEY_REPORT_MASS: getattr(self.section_property, 'mass', ''),
                                        KEY_REPORT_AREA: safe_round(getattr(self.section_property, 'area', 0) * 1e-2, 2),
                                        KEY_REPORT_DEPTH: getattr(self.section_property, 'depth', ''),
                                        KEY_REPORT_WIDTH: getattr(self.section_property, 'flange_width', ''),
                                        KEY_REPORT_WEB_THK: getattr(self.section_property, 'web_thickness', ''),
                                        KEY_REPORT_FLANGE_THK: getattr(self.section_property, 'flange_thickness', ''),
                                        KEY_DISP_FLANGE_S_REPORT: getattr(self.section_property, 'flange_slope', '')}


                self.report_input = \
                    {#KEY_MAIN_MODULE: self.mainmodule,
                    KEY_MODULE: self.module, #"Axial load on column "
                        KEY_DISP_AXIAL: self.load.axial_force * 10 ** -3,
                        KEY_DISP_ACTUAL_LEN_ZZ: self.length_zz,
                        KEY_DISP_ACTUAL_LEN_YY: self.length_yy,
                        KEY_DISP_SEC_PROFILE: self.sec_profile,
                        KEY_DISP_SECSIZE: self.result_section_class,
                        KEY_DISP_END1: self.end_1_z,
                        KEY_DISP_END2: self.end_2_z,
                        KEY_DISP_END1_Y: self.end_1_y,
                        KEY_DISP_END2_Y: self.end_2_y,
                        "Column Section - Mechanical Properties": "TITLE",
                    KEY_MATERIAL: self.material,
                        KEY_DISP_ULTIMATE_STRENGTH_REPORT: self.material_property.fu,
                        KEY_DISP_YIELD_STRENGTH_REPORT: self.material_property.fy,
                        KEY_DISP_EFFECTIVE_AREA_PARA: self.effective_area_factor, #To Check
                        KEY_DISP_SECSIZE:  str(self.sec_list),
                        "Selected Section Details": self.report_column,
                    }

                self.report_check = []
                t1 = ('Selected', 'Selected Member Data', '|p{5cm}|p{2cm}|p{2cm}|p{2cm}|p{4cm}|')
                self.report_check.append(t1)

                self.h = (self.section_property.depth - 2 * (self.section_property.flange_thickness + self.section_property.root_radius))
                self.h_bf_ratio = self.h / self.section_property.flange_width


                # 2.2 CHECK: Buckling Class - Compatibility Check
                t1 = ('SubSection', 'Buckling Class - Compatibility Check', '|p{4cm}|p{3.5cm}|p{6.5cm}|p{2cm}|')
                self.report_check.append(t1)

                # YY axis row
                t1 = (
                    "h/bf and tf for YY Axis", 
                    comp_column_class_section_check_required(self.h, self.section_property.flange_width, self.section_property.flange_thickness, "YY"),  
                    comp_column_class_section_check_provided(self.h, self.section_property.flange_width, self.section_property.flange_thickness, round(self.h_bf_ratio, 2), "YY"), 'Compatible'  
                )
                self.report_check.append(t1)

                # ZZ axis row
                t1 = (
                    "h/bf and tf for ZZ Axis", 
                    comp_column_class_section_check_required(self.h, self.section_property.flange_width, self.section_property.flange_thickness, "ZZ"), 
                    comp_column_class_section_check_provided(self.h, self.section_property.flange_width, self.section_property.flange_thickness, round(self.h_bf_ratio, 2), "ZZ"), 'Compatible'  
                )
                self.report_check.append(t1)

                t1 = ('SubSection', 'Section Classification', '|p{3cm}|p{3.5cm}|p{8.5cm}|p{1cm}|')
                self.report_check.append(t1)
                t1 = ('Web Class', 'Axial Compression',
                        cl_3_7_2_section_classification_web(round(self.h, 2), round(self.section_property.web_thickness, 2), 
                                                          safe_round(safe_classification_value(self.result_designation, 4)),
                                                          self.epsilon, self.section_property.type,
                                                          safe_classification_value(self.result_designation, 2)),
                        ' ')
                self.report_check.append(t1)
                t1 = ('Flange Class', self.section_property.type,
                        cl_3_7_2_section_classification_flange(round(self.section_property.flange_width/2, 2),
                                                            round(self.section_property.flange_thickness, 2),
                                    safe_round(safe_classification_value(self.result_designation, 3)),
                                                            self.epsilon,
                                                            safe_classification_value(self.result_designation, 1)),
                        ' ')
                self.report_check.append(t1)
                t1 = ('Section Class', ' ',
                        cl_3_7_2_section_classification(
                                                            self.input_section_classification[self.result_designation][0]),
                        ' ')
                self.report_check.append(t1)
                

                t1 = ('NewTable', 'Imperfection Factor', '|p{3cm}|p{5 cm}|p{5cm}|p{3 cm}|')
                self.report_check.append(t1)

                t1 = (
                    'YY',
                    self.list_yy[3].upper(),
                    self.list_yy[4], ''
                )
                self.report_check.append(t1)

                t1 = (
                    'ZZ',
                    self.list_zz[3].upper(),
                    self.list_zz[4], ''
                )
                self.report_check.append(t1)


                # Defensive checks for None before division/round
                if self.result_eff_len_yy is not None and self.length_yy:
                    K_yy = self.result_eff_len_yy / self.length_yy
                else:
                    K_yy = None
                if self.result_eff_len_zz is not None and self.length_zz:
                    K_zz = self.result_eff_len_zz / self.length_zz
                else:
                    K_zz = None
                t1 = ('SubSection', 'Slenderness Ratio', '|p{4cm}|p{2 cm}|p{7cm}|p{3 cm}|')
                self.report_check.append(t1)
                val_yy = safe_float(self.result_eff_sr_yy)
                val_zz = safe_float(self.result_eff_sr_zz)
                val_yy_rounded = round(val_yy if val_yy is not None else 0.0, 2)
                val_zz_rounded = round(val_zz if val_zz is not None else 0.0, 2)
                t1 = ("Effective Slenderness Ratio (For YY Axis)", ' ',
                      cl_7_1_2_effective_slenderness_ratio(K_yy, self.length_yy, self.section_property.rad_of_gy_y, val_yy_rounded),
                      ' ')
                self.report_check.append(t1)
                t1 = ("Effective Slenderness Ratio (For ZZ Axis)", ' ',
                      cl_7_1_2_effective_slenderness_ratio(K_zz, self.length_zz, self.section_property.rad_of_gy_z, val_zz_rounded),
                      ' ')
                self.report_check.append(t1)



                t1 = ('SubSection', 'Checks', '|p{4cm}|p{2 cm}|p{7cm}|p{3 cm}|')
                self.report_check.append(t1)
                                
                t1 = (r'$\phi_{yy}$', ' ',
                    cl_8_7_1_5_phi(self.result_IF_yy, safe_round(self.non_dim_eff_sr_yy, 2), safe_round(self.result_phi_yy, 2)),
                    ' ')
                self.report_check.append(t1)

                t1 = (r'$\phi_{zz}$', ' ',
                    cl_8_7_1_5_phi(self.result_IF_zz, safe_round(self.non_dim_eff_sr_zz, 2), safe_round(self.result_phi_zz, 2)),
                    ' ')
                self.report_check.append(t1)

                t1 = (r'$F_{cd,yy} \, \left( \frac{N}{\text{mm}^2} \right)$', ' ',
                    cl_8_7_1_5_Buckling(
                        str(self.material_property.fy) if self.material_property.fy is not None else '',
                        str(self.gamma_m0) if self.gamma_m0 is not None else '',
                        str(safe_round(self.non_dim_eff_sr_yy, 2)),
                        str(safe_round(self.result_phi_yy, 2)),
                        str(safe_round(self.result_fcd_2, 2)),
                        str(safe_round(self.result_fcd_yy, 2)),
                    ),
                    ' ')
                self.report_check.append(t1)

                t1 = (r'$F_{cd,zz} \, \left( \frac{N}{\text{mm}^2} \right)$', ' ',
                    cl_8_7_1_5_Buckling(
                        str(self.material_property.fy) if self.material_property.fy is not None else '',
                        str(self.gamma_m0) if self.gamma_m0 is not None else '',
                        str(safe_round(self.non_dim_eff_sr_zz, 2)),
                        str(safe_round(self.result_phi_zz, 2)),
                        str(safe_round(self.result_fcd_2, 2)),
                        str(safe_round(self.result_fcd_zz, 2)),
                    ),
                    ' ')
                self.report_check.append(t1)

                # Defensive: check for None before division/round for result_capacity and result_fcd
                cap = self.result_capacity if self.result_capacity is not None else 0.0
                fcd = self.result_fcd if self.result_fcd is not None else 0.0
                area = self.section_property.area if self.section_property and hasattr(self.section_property, 'area') else 0.0
                t1 = (r'Design Compressive Strength (\( P_d \)) (For the most critical value of \( F_{cd} \))', self.load.axial_force * 10 ** -3,
                    cl_7_1_2_design_compressive_strength(safe_round(cap / 1000, 2), area, safe_round(fcd, 2), self.load.axial_force * 10 ** -3),
                    get_pass_fail(self.load.axial_force * 10 ** -3, safe_round(cap, 2), relation="leq"))
                self.report_check.append(t1)

            else:
                self.report_input = \
                    {#KEY_MAIN_MODULE: self.mainmodule,
                    KEY_MODULE: self.module, #"Axial load on column "
                        KEY_DISP_AXIAL: self.load.axial_force * 10 ** -3,
                        KEY_DISP_ACTUAL_LEN_ZZ: self.length_zz,
                        KEY_DISP_ACTUAL_LEN_YY: self.length_yy,
                        KEY_DISP_SEC_PROFILE: self.sec_profile,
                        KEY_DISP_SECSIZE:  str(self.sec_list),
                        #KEY_DISP_SECSIZE: self.result_section_class,
                        KEY_DISP_END1: self.end_1_z,
                        KEY_DISP_END2: self.end_2_z,
                        KEY_DISP_END1_Y: self.end_1_y,
                        KEY_DISP_END2_Y: self.end_2_y,
                        "Column Section - Mechanical Properties": "TITLE",
                    KEY_MATERIAL: self.material,
                        KEY_DISP_ULTIMATE_STRENGTH_REPORT: self.material_property.fu,
                        KEY_DISP_YIELD_STRENGTH_REPORT: self.material_property.fy,
                        KEY_DISP_EFFECTIVE_AREA_PARA: self.effective_area_factor, #To Check
                        
                        # "Failed Section Details": self.report_column,
                    }
                self.report_check = []

                t1 = ('Selected', 'All Members Failed', '|p{5cm}|p{2cm}|p{2cm}|p{2cm}|p{4cm}|')
                self.report_check.append(t1)


            Disp_2d_image = []
            Disp_3D_image = "/ResourceFiles/images/3d.png"


            rel_path = str(sys.path[0])
            rel_path = os.path.abspath(".") # TEMP
            rel_path = rel_path.replace("\\", "/")
            fname_no_ext = popup_summary['filename']
            CreateLatex.save_latex(CreateLatex(), self.report_input, self.report_check, popup_summary, fname_no_ext,
                                  rel_path, Disp_2d_image, Disp_3D_image, module=self.module) 
    
    '''   
    def get_end_conditions(self, *args):
        """
        Returns the list of standard end conditions for both y-y and z-z axes.
        These values are used in dropdowns for End 1 and End 2.
        """
        return ["Fixed", "Pinned", "Free"]

    def get_I_sec_properties(self, *args):
        """
        Get I-section properties for display in design preferences.
        This function is called when section designation changes in the Column Section tab.
        """
        if len(args) == 1 and isinstance(args[0], list):
            args = args[0]
        section = args[0] if args else None
        
        if not section or section == 'Select Section':
            return ['', '', '', '', '', '', '', '', '', '', '', '', '']
        
        try:
            # Connect to database to get section properties
            material_grade = self.material if hasattr(self, 'material') and isinstance(self.material, str) else 'Fe250'
            section_property = ISection(designation=section, material_grade=material_grade)
            
            # Return section properties in the expected format
            return [
                str(section_property.depth),  # Label_11
                str(section_property.flange_width),  # Label_12
                str(section_property.web_thickness),  # Label_13
                str(section_property.flange_thickness),  # Label_14
                str(section_property.area),  # Label_15
                str(section_property.mom_inertia_z),  # Label_16
                str(section_property.mom_inertia_y),  # Label_17
                str(section_property.rad_of_gy_z),  # Label_18
                str(section_property.rad_of_gy_y),  # Label_19
                str(section_property.elast_sec_mod_z),  # Label_20
                str(section_property.elast_sec_mod_y),  # Label_21
                str(section_property.plast_sec_mod_z),  # Label_22
                str(files("osdag.data.ResourceFiles.images").joinpath("I_section.png"))  # KEY_IMAGE
            ]
        except Exception as e:
            # Return empty values if there's an error
            return ['', '', '', '', '', '', '', '', '', '', '', '', '']
    '''
    def change_source(self, *args):
        """
        Change source information for the selected section.
        This function is called when section designation changes in the Column Section tab.
        """
        if len(args) == 1 and isinstance(args[0], list):
            args = args[0]
        section = args[0] if args else None
        
        if not section or section == 'Select Section':
            return ''
        
        try:
            # Connect to database to get section source
            material_grade = self.material if hasattr(self, 'material') and isinstance(self.material, str) else 'Fe250'
            section_property = ISection(designation=section, material_grade=material_grade)
            return section_property.source if hasattr(section_property, 'source') else 'IS 808'
        except Exception as e:
            return 'IS 808'  # Default source
    '''
    def get_SHS_RHS_properties(self, *args):
        """
        Get SHS/RHS section properties for display in design preferences.
        This function is called when section designation changes in the Column Section tab.
        """
        if len(args) == 1 and isinstance(args[0], list):
            args = args[0]
        section = args[0] if args else None
        
        if not section or section == 'Select Section':
            return ['', '', '', '', '', '', '', '', '', '', '', '', '']
        
        try:
            # Connect to database to get section properties
            material_grade = self.material if hasattr(self, 'material') and isinstance(self.material, str) else 'Fe250'
            section_property = ISection(designation=section, material_grade=material_grade)
            
            # Return section properties in the expected format for SHS/RHS
            return [
                str(section_property.depth),  # Label_HS_11
                str(section_property.flange_width),  # Label_HS_12
                str(section_property.web_thickness),  # Label_HS_13
                str(section_property.flange_thickness),  # Label_HS_14
                str(section_property.area),  # Label_HS_15
                str(section_property.mom_inertia_z),  # Label_HS_16
                str(section_property.mom_inertia_y),  # Label_HS_17
                str(section_property.rad_of_gy_z),  # Label_HS_18
                str(section_property.rad_of_gy_y),  # Label_HS_19
                str(section_property.elast_sec_mod_z),  # Label_HS_20
                str(section_property.elast_sec_mod_y),  # Label_HS_21
                str(section_property.plast_sec_mod_z),  # Label_HS_22
                str(files("osdag.data.ResourceFiles.images").joinpath("I_section.png"))  # KEY_IMAGE
            ]
        except Exception as e:
            # Return empty values if there's an error
            return ['', '', '', '', '', '', '', '', '', '', '', '', '']

    def get_CHS_properties(self, *args):
        """
        Get CHS section properties for display in design preferences.
        This function is called when section designation changes in the Column Section tab.
        """
        if len(args) == 1 and isinstance(args[0], list):
            args = args[0]
        section = args[0] if args else None
        
        if not section or section == 'Select Section':
            return ['', '', '', '', '', '', '', '', '', '']
        
        try:
            # Connect to database to get section properties
            material_grade = self.material if hasattr(self, 'material') and isinstance(self.material, str) else 'Fe250'
            section_property = ISection(designation=section, material_grade=material_grade)
            
            # Return section properties in the expected format for CHS
            return [
                str(section_property.depth),  # Label_CHS_11
                str(section_property.web_thickness),  # Label_CHS_12
                str(section_property.area),  # Label_CHS_13
                str(section_property.mom_inertia_z),  # Label_HS_14
                str(section_property.mom_inertia_y),  # Label_HS_15
                str(section_property.rad_of_gy_z),  # Label_HS_16
                str(section_property.elast_sec_mod_z),  # Label_21
                str(section_property.plast_sec_mod_z),  # Label_22
                str(files("osdag.data.ResourceFiles.images").joinpath("I_section.png"))  # KEY_IMAGE
            ]
        except Exception as e:
            # Return empty values if there's an error
            return ['', '', '', '', '', '', '', '', '', '']
    
    def get_fu_fy_I_section(self, *args):
        """
        Override to accept arguments as passed from tab_change (material, designation_dict).
        Handles both single and multiple selections robustly.
        """
        if len(args) < 2:
            return {}
        material_grade = args[0]
        designation_dict = args[1]
        # Defensive: handle both dict and string for designation
        designation = None
        if isinstance(designation_dict, dict):
            designation = designation_dict.get(KEY_SECSIZE, "Select Section")
        elif isinstance(designation_dict, str):
            designation = designation_dict
        else:
            designation = "Select Section"
        # Handle multiple selections (list)
        if isinstance(designation, list):
            designation = designation[0] if designation else "Select Section"
        if isinstance(material_grade, list):
            material_grade = material_grade[0] if material_grade else "Select Material"
        fu = ''
        fy = ''
        if material_grade != "Select Material" and designation != "Select Section":
            table = "Beams" if designation in connectdb("Beams", "popup") else "Columns"
            I_sec_attributes = ISection(designation)
            I_sec_attributes.connect_to_database_update_other_attributes(table, designation, material_grade)
            fu = str(I_sec_attributes.fu)
            fy = str(I_sec_attributes.fy)
        d = {KEY_SUPTNGSEC_FU: fu,
             KEY_SUPTNGSEC_FY: fy,
             KEY_SUPTDSEC_FU: fu,
             KEY_SUPTDSEC_FY: fy,
             KEY_SEC_FU: fu,
             KEY_SEC_FY: fy}
        return d
    '''
    def close_module(self):
        """
        Called when the LacedColumn module is closed. Resets all input and output state, and closes any background windows/tabs (like design preferences) that may be open.
        """
        print("[DEBUG][close_module] Closing LacedColumn module: resetting state and closing background windows.")
        # Reset all output/calculated fields
        self.reset_output_state()
        # Reset all input fields (QLineEdit, QComboBox, etc.)
        if hasattr(self, 'unsupported_length_yy_lineedit'):
            self.unsupported_length_yy_lineedit.setText("")
        if hasattr(self, 'unsupported_length_zz_lineedit'):
            self.unsupported_length_zz_lineedit.setText("")
        if hasattr(self, 'axial_load_lineedit'):
            self.axial_load_lineedit.setText("")
        if hasattr(self, 'material_combo'):
            self.material_combo.setCurrentIndex(0)
        if hasattr(self, 'connection_combo'):
            self.connection_combo.setCurrentIndex(0)
        if hasattr(self, 'lacing_pattern_combo'):
            self.lacing_pattern_combo.setCurrentIndex(0)
        if hasattr(self, 'section_profile_combo'):
            self.section_profile_combo.setCurrentIndex(0)
        if hasattr(self, 'section_designation_combo'):
            self.section_designation_combo.setCurrentIndex(0)
        if hasattr(self, 'design_pref_dialog') and self.design_pref_dialog is not None:
            try:
                self.design_pref_dialog.close()
            except Exception:
                pass
            self.design_pref_dialog = None
        self.sec_list = []
        self.material = ""
        print("[DEBUG][close_module] State reset complete.")

    def open_module(self):
        """
        Called when the LacedColumn module is opened. Ensures all input/output state is reset (fresh start).
        """
        print("[DEBUG][open_module] Opening LacedColumn module: resetting state.")
        self.close_module()  # Always reset on open
        print("[DEBUG][open_module] State reset complete.")

    # Ensure all dialogs are modal and do not close the main window
    def show_dialog(self, dialog):
        """
        Utility to show a dialog modally, ensuring it does not affect the main window's state.
        """
        dialog.setModal(True)
        dialog.exec_()

class SectionDesignationDialog(QDialog):
    def __init__(self, section_list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Section Designations")
        self.setModal(True)
        self.selected_sections = []
        layout = QVBoxLayout(self)
        self.list_widget = QListWidget()
        self.list_widget.addItems(section_list)
        self.list_widget.setSelectionMode(QListWidget.MultiSelection)
        layout.addWidget(self.list_widget)
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def get_selected(self):
        return [item.text() for item in self.list_widget.selectedItems()]
    
    '''
    def get_section_class(self, flange_class, web_class):
        # Helper to determine section class from flange and web
        if flange_class == 'Plastic' and web_class == 'Plastic':
            return 'Plastic'
        elif 'Plastic' in [flange_class, web_class] and 'Compact' in [flange_class, web_class]:
            return 'Compact'
        elif 'Plastic' in [flange_class, web_class] and 'Semi-Compact' in [flange_class, web_class]:
            return 'Semi-Compact'
        elif flange_class == 'Compact' and web_class == 'Compact':
            return 'Compact'
        elif 'Compact' in [flange_class, web_class] and 'Semi-Compact' in [flange_class, web_class]:
            return 'Semi-Compact'
        elif flange_class == 'Semi-Compact' and web_class == 'Semi-Compact':
            return 'Semi-Compact'
        else:
            return 'Slender'
    '''

def safe_float(val):
    try:
        return float(val)
    except Exception:
        return 0.0
