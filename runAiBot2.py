'''
Author:     Sai Vignesh Golla
LinkedIn:   https://www.linkedin.com/in/saivigneshgolla/

Copyright (C) 2024 Sai Vignesh Golla

License:    GNU Affero General Public License
            https://www.gnu.org/licenses/agpl-3.0.en.html
            
GitHub:     https://github.com/GodsScion/Auto_job_applier_linkedIn

version:    24.12.29.12.30
'''


# Imports
import os
import csv
import re
import pyautogui
import unicodedata
from decimal import Decimal, InvalidOperation

from random import choice, shuffle
from datetime import datetime

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.select import Select
from selenium.webdriver.remote.webelement import WebElement
from selenium.common.exceptions import NoSuchElementException, ElementClickInterceptedException, NoSuchWindowException, ElementNotInteractableException

from config.personals import *
from config.questions import *
from config.search import *
from config.secrets import use_AI, username, password
from config.settings import *

from modules.open_chrome import *
from modules.helpers import *
from modules.clickers_and_finders import *
from modules.validator import validate_config
from modules.ai.openaiConnections import *
from modules.ai.answer_review_queue import AIAnswerReviewQueue
from modules.ai.gemini_unknown_question import (
    answer_deterministic_question,
    answer_unknown_question,
    answer_verified_question,
    is_experience_capability_question,
    is_citizenship_question,
    is_protected_objective_fact_question,
)

from typing import Literal

# #kkkkkkkk
# import config.settings as _settings
# print_lg(f"[DEBUG] settings loaded from: {_settings.__file__}")
# print_lg(f"[DEBUG] pause_after_filters={pause_after_filters}, switch_number={switch_number}, run_in_background={run_in_background}, run_non_stop={run_non_stop}")
# #kkkkkkkk

pyautogui.FAILSAFE = False
# if use_resume_generator:    from resume_generator import is_logged_in_GPT, login_GPT, open_resume_chat, create_custom_resume


#< Global Variables and logics

if run_in_background == True:
    pause_at_failed_question = False
    pause_before_submit = False
    run_non_stop = False

first_name = first_name.strip()
middle_name = middle_name.strip()
last_name = last_name.strip()
full_name = first_name + " " + middle_name + " " + last_name if middle_name else first_name + " " + last_name

useNewResume = True
randomly_answered_questions = set()

tabs_count = 1
easy_applied_count = 0
external_jobs_count = 0
failed_count = 0
skip_count = 0
dailyEasyApplyLimitReached = False

re_experience = re.compile(r'[(]?\s*(\d+)\s*[)]?\s*[-to]*\s*\d*[+]*\s*year[s]?', re.IGNORECASE)

desired_salary_lakhs = str(round(desired_salary / 100000, 2))
desired_salary_monthly = str(round(desired_salary/12, 2))
desired_salary = str(desired_salary)

current_ctc_lakhs = str(round(current_ctc / 100000, 2))
current_ctc_monthly = str(round(current_ctc/12, 2))
current_ctc = str(current_ctc)

notice_period_months = str(notice_period//30)
notice_period_weeks = str(notice_period//7)
notice_period = str(notice_period)

aiClient = None
ai_answer_review_queue = None
ai_review_context = {}
##> ------ Dheeraj Deshwal : dheeraj9811 Email:dheeraj20194@iiitd.ac.in/dheerajdeshwal9811@gmail.com - Feature ------
about_company_for_ai = None # TODO extract about company for AI
##<


#>


#< Login Functions
# def is_logged_in_LN() -> bool:
#     '''
#     Function to check if user is logged-in in LinkedIn
#     * Returns: `True` if user is logged-in or `False` if not
#     '''
#     if driver.current_url == "https://www.linkedin.com/feed/": return True
#     if try_linkText(driver, "Sign in"): return False
#     if try_xp(driver, '//button[@type="submit" and contains(text(), "Sign in")]'):  return False
#     if try_linkText(driver, "Join now"): return False
#     print_lg("Didn't find Sign in link, so assuming user is logged in!")
#     return True
def is_logged_in_LN() -> bool:
    '''
    Strict login check.
    Never assume logged in just because Sign in link is missing.
    '''
    try:
        driver.get("https://www.linkedin.com/feed/")
        sleep(3)

        current_url = driver.current_url.lower()
        page = driver.page_source.lower()

        print_lg(f"DEBUG login check url: {driver.current_url}")

        # Clearly logged out / login page
        if "login" in current_url or "signup" in current_url:
            print_lg("DEBUG: login check failed - redirected to login/signup.")
            return False

        # LinkedIn guest pages / auth wall / anonymous pages
        if "authwall" in current_url or "trk=public" in current_url:
            print_lg("DEBUG: login check failed - guest/authwall page.")
            return False

        # Login words in English or Spanish
        logged_out_words = [
            "sign in",
            "join now",
            "forgot password",
            "iniciar sesión",
            "únete ahora",
            "has olvidado tu contraseña",
            "regístrate",
        ]

        if any(word in page for word in logged_out_words):
            print_lg("DEBUG: login check failed - logged out text detected.")
            return False

        # Strong logged-in indicators
        logged_in_words = [
            "start a post",
            "crear publicación",
            "mi red",
            "messaging",
            "mensajes",
            "notifications",
            "notificaciones",
        ]

        if "/feed" in current_url and any(word in page for word in logged_in_words):
            print_lg("DEBUG: login check passed - feed and logged-in UI detected.")
            return True

        print_lg("DEBUG: login check uncertain. Treating as NOT logged in.")
        return False

    except Exception as e:
        print_lg("DEBUG: login check exception. Treating as NOT logged in.", e)
        return False


def login_LN() -> None:
    '''
    Function to login for LinkedIn
    * Tries to login using given `username` and `password` from `secrets.py`
    * If failed, tries to login using saved LinkedIn profile button if available
    * If both failed, asks user to login manually
    '''
    # Find the username and password fields and fill them with user credentials
    driver.get("https://www.linkedin.com/login")
    try:
        # wait.until(EC.presence_of_element_located((By.LINK_TEXT, "Forgot password?")))
        # try:
        #     text_input_by_ID(driver, "username", username, 1)
        # except Exception as e:
        #     print_lg("Couldn't find username field.")
        #     # print_lg(e)
        # try:
        #     text_input_by_ID(driver, "password", password, 1)
        # except Exception as e:
        #     print_lg("Couldn't find password field.")
        #     # print_lg(e)
        # # Find the login submit button and click it
        # driver.find_element(By.XPATH, '//button[@type="submit" and contains(text(), "Sign in")]').click()
        wait.until(
            EC.presence_of_element_located(
                (By.XPATH, "//input[@type='email' and contains(@autocomplete, 'username')]")
            )
        )

        username_field = next(
            el for el in driver.find_elements(
                By.XPATH,
                "//input[@type='email' and contains(@autocomplete, 'username')]"
            )
            if el.is_displayed() and el.is_enabled()
        )

        password_field = next(
            el for el in driver.find_elements(
                By.XPATH,
                "//input[@type='password' and @autocomplete='current-password']"
            )
            if el.is_displayed() and el.is_enabled()
        )

        username_field.click()
        username_field.clear()
        username_field.send_keys(username)

        password_field.click()
        password_field.clear()
        password_field.send_keys(password)

        sleep(1)
        password_field.send_keys(Keys.ENTER)
        sleep(8)

        pyautogui.alert(
            "Please check the LinkedIn window now.\n\n"
            "If LinkedIn asks for verification, captcha, email code, or checkpoint, finish it manually.\n\n"
            "Only click OK after you can see the LinkedIn home/feed page.",
            "Finish LinkedIn Login"
        )
    except Exception as e1:
        try:
            profile_button = find_by_class(driver, "profile__details")
            profile_button.click()
        except Exception as e2:
            # print_lg(e1, e2)
            print_lg("Couldn't Login!")

    try:
        # Wait until successful redirect, indicating successful login
        wait.until(EC.url_to_be("https://www.linkedin.com/feed/")) # wait.until(EC.presence_of_element_located((By.XPATH, '//button[normalize-space(.)="Start a post"]')))
        return print_lg("Login successful!")
    except Exception as e:
        print_lg("Seems like login attempt failed! Possibly due to wrong credentials or already logged in! Try logging in manually!")
        # print_lg(e)
        manual_login_retry(is_logged_in_LN, 2)
#>



def get_applied_job_ids() -> set:
    '''
    Function to get a `set` of applied job's Job IDs
    * Returns a set of Job IDs from existing applied jobs history csv file
    '''
    job_ids = set()
    try:
        with open(file_name, 'r', encoding='utf-8') as file:
            reader = csv.reader(file)
            for row in reader:
                job_ids.add(row[0])
    except FileNotFoundError:
        print_lg(f"The CSV file '{file_name}' does not exist.")
    return job_ids



def set_search_location() -> None:
    '''
    Function to set search location
    '''
    if search_location.strip():
        try:
            print_lg(f'Setting search location as: "{search_location.strip()}"')
            search_location_ele = try_xp(driver, ".//input[@aria-label='City, state, or zip code'and not(@disabled)]", False) #  and not(@aria-hidden='true')]")
            text_input(actions, search_location_ele, search_location, "Search Location")
        except ElementNotInteractableException:
            try_xp(driver, ".//label[@class='jobs-search-box__input-icon jobs-search-box__keywords-label']")
            actions.send_keys(Keys.TAB, Keys.TAB).perform()
            actions.key_down(Keys.CONTROL).send_keys("a").key_up(Keys.CONTROL).perform()
            actions.send_keys(search_location.strip()).perform()
            sleep(2)
            actions.send_keys(Keys.ENTER).perform()
            try_xp(driver, ".//button[@aria-label='Cancel']")
        except Exception as e:
            try_xp(driver, ".//button[@aria-label='Cancel']")
            print_lg("Failed to update search location, continuing with default location!", e)


def apply_filters() -> None:
    '''
    Function to apply job search filters
    '''
    print_lg("DEBUG: apply_filters() started")
    set_search_location()

    try:
        recommended_wait = 1 if click_gap < 1 else 0

        wait.until(EC.presence_of_element_located((By.XPATH, '//button[normalize-space()="All filters"]'))).click()
        buffer(recommended_wait)

        wait_span_click(driver, sort_by)
        wait_span_click(driver, date_posted)
        buffer(recommended_wait)

        multi_sel_noWait(driver, experience_level) 
        multi_sel_noWait(driver, companies, actions)
        if experience_level or companies: buffer(recommended_wait)

        multi_sel_noWait(driver, job_type)
        multi_sel_noWait(driver, on_site)
        if job_type or on_site: buffer(recommended_wait)

        if easy_apply_only: boolean_button_click(driver, actions, "Easy Apply")
        
        multi_sel_noWait(driver, location)
        multi_sel_noWait(driver, industry)
        if location or industry: buffer(recommended_wait)

        multi_sel_noWait(driver, job_function)
        multi_sel_noWait(driver, job_titles)
        if job_function or job_titles: buffer(recommended_wait)

        if under_10_applicants: boolean_button_click(driver, actions, "Under 10 applicants")
        if in_your_network: boolean_button_click(driver, actions, "In your network")
        if fair_chance_employer: boolean_button_click(driver, actions, "Fair Chance Employer")

        wait_span_click(driver, salary)
        buffer(recommended_wait)
        
        multi_sel_noWait(driver, benefits)
        multi_sel_noWait(driver, commitments)
        if benefits or commitments: buffer(recommended_wait)

        # show_results_button: WebElement = driver.find_element(By.XPATH, '//button[contains(@aria-label, "Apply current filters to show")]')
        # show_results_button.click()

        # global pause_after_filters
        # if pause_after_filters and "Turn off Pause after search" == pyautogui.confirm("These are your configured search results and filter. It is safe to change them while this dialog is open, any changes later could result in errors and skipping this search run.", "Please check your results", ["Turn off Pause after search", "Look's good, Continue"]):
        #     pause_after_filters = True
        # print_lg("DEBUG: trying to find Show results button")
        # print_lg("DEBUG: listing buttons before Show results search")
        # buttons = driver.find_elements(By.TAG_NAME, "button")
        # for i, b in enumerate(buttons):
        #     try:
        #         txt = b.text
        #         aria = b.get_attribute("aria-label")
        #         cls = b.get_attribute("class")
        #         displayed = b.is_displayed()
        #         enabled = b.is_enabled()
        #         print_lg(f"DEBUG BUTTON {i}: text=[{txt}] aria=[{aria}] displayed={displayed} enabled={enabled} class=[{cls}]")
        #     except Exception as e:
        #         print_lg(f"DEBUG BUTTON {i}: failed to inspect button: {e}")
        # show_results_button: WebElement = driver.find_element(
        #     By.XPATH,
        #     '//button[contains(@aria-label, "Apply current filters to show") or contains(@aria-label, "Mostrar")]'
        # )

        # print_lg("DEBUG: Show results button found, clicking")
        # show_results_button.click()

        # sleep(3)

        # global pause_after_filters
        # print_lg(f"DEBUG: pause_after_filters = {pause_after_filters}")

        # if pause_after_filters:
        #     print_lg("DEBUG: showing pause_after_filters dialog")

        #     decision = pyautogui.confirm(
        #         "Please check the LinkedIn search results now.\n\n"
        #         "You can manually adjust filters while this dialog is open.\n\n"
        #         "Click Continue when the search results look good.",
        #         "Pause after search",
        #         ["Turn off Pause after search", "Continue"]
        #     )

        #     print_lg(f"DEBUG: pause dialog decision = {decision}")

        #     if decision == "Turn off Pause after search":
        #         pause_after_filters = False
        print_lg("DEBUG: trying to find Show results button")

        try:
            show_results_button: WebElement = driver.find_element(
                By.XPATH,
                "//button["
                "contains(translate(@aria-label, 'ABCDEFGHIJKLMNOPQRSTUVWXYZÁÉÍÓÚ', 'abcdefghijklmnopqrstuvwxyzáéíóú'), 'show') "
                "or contains(translate(@aria-label, 'ABCDEFGHIJKLMNOPQRSTUVWXYZÁÉÍÓÚ', 'abcdefghijklmnopqrstuvwxyzáéíóú'), 'mostrar') "
                "or contains(translate(@aria-label, 'ABCDEFGHIJKLMNOPQRSTUVWXYZÁÉÍÓÚ', 'abcdefghijklmnopqrstuvwxyzáéíóú'), 'result') "
                "or contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZÁÉÍÓÚ', 'abcdefghijklmnopqrstuvwxyzáéíóú'), 'show') "
                "or contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZÁÉÍÓÚ', 'abcdefghijklmnopqrstuvwxyzáéíóú'), 'mostrar') "
                "or contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZÁÉÍÓÚ', 'abcdefghijklmnopqrstuvwxyzáéíóú'), 'result')"
                "]"
            )

            print_lg("DEBUG: Show results button found, clicking")
            show_results_button.click()
            sleep(3)

        except Exception as e:
            print_lg("DEBUG: Show results button not found or not clickable.")
            print_lg(e)
            print_lg("DEBUG: continuing to manual pause anyway.")

        global pause_after_filters
        print_lg(f"DEBUG: pause_after_filters = {pause_after_filters}")

        if pause_after_filters:
            print_lg("DEBUG: showing pause_after_filters dialog")

            decision = pyautogui.confirm(
                "Please check the LinkedIn search results now.\n\n"
                "You can manually adjust filters while this dialog is open.\n\n"
                "Click Continue when the search results look good.",
                "Pause after search",
                ["Turn off Pause after search", "Continue"]
            )

            print_lg(f"DEBUG: pause dialog decision = {decision}")

            if decision == "Turn off Pause after search":
                pause_after_filters = False

    except Exception as e:
        print_lg("Setting the preferences failed!")
        print_lg(e)



def get_page_info() -> tuple[WebElement | None, int | None]:
    '''
    Function to get pagination element and current page number
    '''
    try:
        pagination_element = try_find_by_classes(driver, ["artdeco-pagination", "artdeco-pagination__pages"])
        scroll_to_view(driver, pagination_element)
        current_page = int(pagination_element.find_element(By.XPATH, "//li[contains(@class, 'active')]").text)
    except Exception as e:
        print_lg("Failed to find Pagination element, hence couldn't scroll till end!")
        pagination_element = None
        current_page = None
        print_lg(e)
    return pagination_element, current_page



def get_job_main_details(job: WebElement, blacklisted_companies: set, rejected_jobs: set) -> tuple[str, str, str, str, str, bool]:
    '''
    # Function to get job main details.
    Returns a tuple of (job_id, title, company, work_location, work_style, skip)
    * job_id: Job ID
    * title: Job title
    * company: Company name
    * work_location: Work location of this job
    * work_style: Work style of this job (Remote, On-site, Hybrid)
    * skip: A boolean flag to skip this job
    '''
    job_details_button = job.find_element(By.TAG_NAME, 'a')  # job.find_element(By.CLASS_NAME, "job-card-list__title")  # Problem in India
    scroll_to_view(driver, job_details_button, True)
    #Jinhao
    try:
        inner_div = job.find_element(By.XPATH, ".//div[contains(@class, 'job-card-container--clickable')]")
        job_id = inner_div.get_attribute("data-job-id")
    except Exception as e:
        print(f"⚠️ Failed to get job_id: {e}")
        job_id = "unknown"
    #CR:Jinhao
    #job_id = job.get_dom_attribute('data-occludable-job-id')
    title = job_details_button.text
    title = title[:title.find("\n")]
    # company = job.find_element(By.CLASS_NAME, "job-card-container__primary-description").text
    # work_location = job.find_element(By.CLASS_NAME, "job-card-container__metadata-item").text
    other_details = job.find_element(By.CLASS_NAME, 'artdeco-entity-lockup__subtitle').text
    index = other_details.find(' · ')
    company = other_details[:index]
    work_location = other_details[index+3:]
    work_style = work_location[work_location.rfind('(')+1:work_location.rfind(')')]
    work_location = work_location[:work_location.rfind('(')].strip()
    
    # Skip if previously rejected due to blacklist or already applied
    skip = False
   
    # Skip jobs that were manually dismissed/hidden from the LinkedIn results list
    try:
        card_text = job.text.lower()
        card_html = job.get_attribute("innerHTML").lower()

        if (
           "job-card-list--is-dismissed" in card_html

            or "we won’t show you this job again" in card_text

            or "we won't show you this job again" in card_text

            or "was dismissed" in card_text

            or "deshacer" in card_text
        ):
            print_lg(f'Skipping manually dismissed/hidden job "{title} | {company}". Job ID: {job_id}!')
            skip = True

    except Exception as e:
        print_lg("Could not check whether job card was dismissed/hidden.")
        print_lg(e)
    if company in blacklisted_companies:
        print_lg(f'Skipping "{title} | {company}" job (Blacklisted Company). Job ID: {job_id}!')
        skip = True
    elif job_id in rejected_jobs: 
        print_lg(f'Skipping previously rejected "{title} | {company}" job. Job ID: {job_id}!')
        skip = True
    try:
        if job.find_element(By.CLASS_NAME, "job-card-container__footer-job-state").text == "Applied":
            skip = True
            print_lg(f'Already applied to "{title} | {company}" job. Job ID: {job_id}!')
    except: pass
    try: 
        if not skip: job_details_button.click()
    except Exception as e:
        print_lg(f'Failed to click "{title} | {company}" job on details button. Job ID: {job_id}!') 
        # print_lg(e)
        cleanup_result = _guard_next_job_click(driver, job_id)
        if not cleanup_result["success"]:
            raise RuntimeError("easy_apply_modal_cleanup_failed")
        job_details_button.click() # To pass non-modal click errors outside
    buffer(click_gap)
    return (job_id,title,company,work_location,work_style,skip)


# Function to check for Blacklisted words in About Company
def check_blacklist(rejected_jobs: set, job_id: str, company: str, blacklisted_companies: set) -> tuple[set, set, WebElement] | ValueError:
    jobs_top_card = try_find_by_classes(driver, ["job-details-jobs-unified-top-card__primary-description-container","job-details-jobs-unified-top-card__primary-description","jobs-unified-top-card__primary-description","jobs-details__main-content"])
    about_company_org = find_by_class(driver, "jobs-company__box")
    scroll_to_view(driver, about_company_org)
    about_company_org = about_company_org.text
    about_company = about_company_org.lower()
    skip_checking = False
    for word in about_company_good_words:
        if word.lower() in about_company:
            print_lg(f'Found the word "{word}". So, skipped checking for blacklist words.')
            skip_checking = True
            break
    if not skip_checking:
        for word in about_company_bad_words: 
            if word.lower() in about_company: 
                rejected_jobs.add(job_id)
                blacklisted_companies.add(company)
                raise ValueError(f'\n"{about_company_org}"\n\nContains "{word}".')
    buffer(click_gap)
    scroll_to_view(driver, jobs_top_card)
    return rejected_jobs, blacklisted_companies, jobs_top_card



# Function to extract years of experience required from About Job
def extract_years_of_experience(text: str) -> int:
    # Extract all patterns like '10+ years', '5 years', '3-5 years', etc.
    matches = re.findall(re_experience, text)
    if len(matches) == 0: 
        print_lg(f'\n{text}\n\nCouldn\'t find experience requirement in About the Job!')
        return 0
    return max([int(match) for match in matches if int(match) <= 12])



def get_job_description(
) -> tuple[
    str | Literal['Unknown'],
    int | Literal['Unknown'],
    bool,
    str | None,
    str | None
    ]:
    '''
    # Job Description
    Function to extract job description from About the Job.
    ### Returns:
    - `jobDescription: str | 'Unknown'`
    - `experience_required: int | 'Unknown'`
    - `skip: bool`
    - `skipReason: str | None`
    - `skipMessage: str | None`
    '''
    try:
        ##> ------ Dheeraj Deshwal : dheeraj9811 Email:dheeraj20194@iiitd.ac.in/dheerajdeshwal9811@gmail.com - Feature ------
        jobDescription = "Unknown"
        ##<

        experience_required = "Unknown"
        found_masters = 0
        jobDescription = find_by_class(driver, "jobs-box__html-content").text
        jobDescriptionLow = jobDescription.lower()
        skip = False
        skipReason = None
        skipMessage = None
        for word in bad_words:
            if word.lower() in jobDescriptionLow:
                skipMessage = f'\n{jobDescription}\n\nContains bad word "{word}". Skipping this job!\n'
                skipReason = "Found a Bad Word in About Job"
                skip = True
                break
        if not skip and security_clearance == False and ('polygraph' in jobDescriptionLow or 'clearance' in jobDescriptionLow or 'secret' in jobDescriptionLow):
            skipMessage = f'\n{jobDescription}\n\nFound "Clearance" or "Polygraph". Skipping this job!\n'
            skipReason = "Asking for Security clearance"
            skip = True
        if not skip:
            if did_masters and 'master' in jobDescriptionLow:
                print_lg(f'Found the word "master" in \n{jobDescription}')
                found_masters = 2
            experience_required = extract_years_of_experience(jobDescription)
            if current_experience > -1 and experience_required > current_experience + found_masters:
                skipMessage = f'\n{jobDescription}\n\nExperience required {experience_required} > Current Experience {current_experience + found_masters}. Skipping this job!\n'
                skipReason = "Required experience is high"
                skip = True
    except Exception as e:
        if jobDescription == "Unknown":    print_lg("Unable to extract job description!")
        else:
            experience_required = "Error in extraction"
            print_lg("Unable to extract years of experience required!")
            # print_lg(e)
    finally:
        return jobDescription, experience_required, skip, skipReason, skipMessage
        


# Function to upload resume
def upload_resume(modal: WebElement, resume: str) -> tuple[bool, str]:
    try:
        modal.find_element(By.NAME, "file").send_keys(os.path.abspath(resume))
        return True, os.path.basename(default_resume_path)
    except: return False, "Previous resume"

# Function to answer common questions for Easy Apply
def answer_common_questions(label: str, answer: str) -> str:
    return answer


def _normalized_form_text(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").casefold())
    text = "".join(character for character in text if not unicodedata.combining(character))
    text = text.replace(".", "")
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def _is_resume_attachment_question(question_text: str) -> bool:
    question = _normalized_form_text(question_text)
    has_resume_term = re.search(
        r"\b(?:cv|resume|curriculum)\b", question
    ) is not None
    has_attachment_intent = any(
        phrase in question
        for phrase in (
            "attach",
            "attached",
            "provide",
            "adjunta",
            "adjuntado",
            "adjunto",
            "proporciona",
        )
    )
    return has_resume_term and has_attachment_intent


def _localized_positive_option(options: list[str]) -> str | None:
    for option in options:
        if _normalized_form_text(option) in {"yes", "si"}:
            return option
    return None


def _resume_selected_in_modal(modal: WebElement) -> bool:
    """Use only current-modal UI state; never infer from configured files."""
    selected_card_xpath = (
        './/*['
        '(contains(translate(@class,"ABCDEFGHIJKLMNOPQRSTUVWXYZ","abcdefghijklmnopqrstuvwxyz"),"resume") '
        'or contains(translate(@data-test,"ABCDEFGHIJKLMNOPQRSTUVWXYZ","abcdefghijklmnopqrstuvwxyz"),"resume") '
        'or contains(translate(@class,"ABCDEFGHIJKLMNOPQRSTUVWXYZ","abcdefghijklmnopqrstuvwxyz"),"document-upload")) '
        'and (contains(translate(@class,"ABCDEFGHIJKLMNOPQRSTUVWXYZ","abcdefghijklmnopqrstuvwxyz"),"selected") '
        'or @aria-selected="true" or @data-selected="true" '
        'or @data-test-document-uploaded="true")]'
    )
    try:
        for card in modal.find_elements(By.XPATH, selected_card_xpath):
            try:
                if not hasattr(card, "is_displayed") or card.is_displayed():
                    return True
            except Exception:
                continue
    except Exception:
        pass

    resume_radio_xpath = (
        './/input[@type="radio" and ancestor::*['
        'contains(translate(@class,"ABCDEFGHIJKLMNOPQRSTUVWXYZ","abcdefghijklmnopqrstuvwxyz"),"resume") '
        'or contains(translate(@data-test,"ABCDEFGHIJKLMNOPQRSTUVWXYZ","abcdefghijklmnopqrstuvwxyz"),"resume") '
        'or contains(translate(@class,"ABCDEFGHIJKLMNOPQRSTUVWXYZ","abcdefghijklmnopqrstuvwxyz"),"document-upload")]]'
    )
    try:
        if any(radio.is_selected() for radio in modal.find_elements(By.XPATH, resume_radio_xpath)):
            return True
    except Exception:
        pass

    uploaded_resume_xpath = (
        './/*['
        '(contains(translate(@class,"ABCDEFGHIJKLMNOPQRSTUVWXYZ","abcdefghijklmnopqrstuvwxyz"),"resume") '
        'or contains(translate(@data-test,"ABCDEFGHIJKLMNOPQRSTUVWXYZ","abcdefghijklmnopqrstuvwxyz"),"resume")) '
        'and (contains(translate(@class,"ABCDEFGHIJKLMNOPQRSTUVWXYZ","abcdefghijklmnopqrstuvwxyz"),"uploaded") '
        'or @data-test-document-uploaded="true")]'
    )
    try:
        for uploaded in modal.find_elements(By.XPATH, uploaded_resume_xpath):
            try:
                if not hasattr(uploaded, "is_displayed") or uploaded.is_displayed():
                    return True
            except Exception:
                continue
    except Exception:
        pass

    file_input_xpath = (
        './/input[@type="file" and ('
        'contains(translate(@name,"ABCDEFGHIJKLMNOPQRSTUVWXYZ","abcdefghijklmnopqrstuvwxyz"),"resume") '
        'or contains(translate(@id,"ABCDEFGHIJKLMNOPQRSTUVWXYZ","abcdefghijklmnopqrstuvwxyz"),"resume") '
        'or contains(translate(@aria-label,"ABCDEFGHIJKLMNOPQRSTUVWXYZ","abcdefghijklmnopqrstuvwxyz"),"resume") '
        'or contains(translate(@name,"ABCDEFGHIJKLMNOPQRSTUVWXYZ","abcdefghijklmnopqrstuvwxyz"),"cv") '
        'or contains(translate(@id,"ABCDEFGHIJKLMNOPQRSTUVWXYZ","abcdefghijklmnopqrstuvwxyz"),"cv"))]'
    )
    try:
        return any(
            bool(str(file_input.get_attribute("value") or "").strip())
            for file_input in modal.find_elements(By.XPATH, file_input_xpath)
        )
    except Exception:
        return False


def _is_required(question: WebElement, control: WebElement) -> bool:
    return any(
        str(element.get_attribute(attribute) or "").lower() in {"true", "required"}
        for element in (question, control) for attribute in ("required", "aria-required")
    )


def _validation_details(control: WebElement) -> tuple[str, dict]:
    try:
        message = str(control.get_property("validationMessage") or "").strip()
    except Exception:
        message = ""
    try:
        validity = control.get_property("validity") or {}
        if not isinstance(validity, dict):
            validity = {}
    except Exception:
        validity = {}
    return message, validity


def _field_constraints(control: WebElement) -> dict[str, str]:
    constraints = {}
    for name in (
        "type",
        "inputmode",
        "min",
        "max",
        "step",
        "required",
        "aria-required",
    ):
        try:
            value = control.get_attribute(name)
        except Exception:
            value = None
        if value not in (None, ""):
            constraints[name] = str(value)[:40]
    return constraints


def _numeric_intent_from_question(question_text: str) -> bool:
    text = re.sub(r"\s+", " ", str(question_text or "").casefold())
    scale_range = re.search(
        r"(?:\(|\b)1\s*(?:-|–|—|to|a)\s*5(?:\)|\b)", text
    )
    scale_words = any(
        phrase in text
        for phrase in (
            "on a scale of",
            "en una escala de",
            "numeric rating",
            "numeric level",
            "rating numérica",
            "rating numerica",
            "nivel numérico",
            "nivel numerico",
        )
    )
    return bool(scale_range or scale_words)


def _is_numeric_control(control: WebElement, question_text: str = "") -> bool:
    input_type = str(control.get_attribute("type") or "").casefold()
    input_mode = str(control.get_attribute("inputmode") or "").casefold()
    has_numeric_constraint = any(
        control.get_attribute(attribute) not in (None, "")
        for attribute in ("min", "max", "step")
    )
    message, validity = _validation_details(control)
    numeric_validation = any(
        marker in message.casefold()
        for marker in (
            "number",
            "decimal",
            "larger than",
            "greater than",
            "número",
            "numero",
            "numérico",
            "numerico",
        )
    ) or any(
        bool(validity.get(flag))
        for flag in (
            "badInput",
            "typeMismatch",
            "rangeUnderflow",
            "rangeOverflow",
            "stepMismatch",
        )
    )
    return (
        input_type == "number"
        or input_mode in {"numeric", "decimal"}
        or has_numeric_constraint
        or _numeric_intent_from_question(question_text)
        or numeric_validation
    )


def _validation_category(control: WebElement) -> str:
    message, validity = _validation_details(control)
    if any(bool(validity.get(flag)) for flag in ("badInput", "typeMismatch")):
        return "numeric_type_mismatch"
    if any(bool(validity.get(flag)) for flag in ("rangeUnderflow", "rangeOverflow", "stepMismatch")):
        return "numeric_range_invalid"
    normalized = message.casefold()
    if any(marker in normalized for marker in ("number", "decimal", "número", "numero")):
        return "numeric_validation_message"
    if str(control.get_attribute("aria-invalid") or "").casefold() == "true":
        return "aria_invalid"
    return "required_value_missing" if not str(control.get_attribute("value") or "").strip() else "browser_invalid"


def _plain_decimal(value) -> Decimal | None:
    match = re.search(r"[-+]?\d[\d\s.,]*", str(value or ""))
    if match is None:
        return None
    token = re.sub(r"\s+", "", match.group(0))
    if "," in token and "." in token:
        if token.rfind(",") > token.rfind("."):
            token = token.replace(".", "").replace(",", ".")
        else:
            token = token.replace(",", "")
    elif "," in token or "." in token:
        separator = "," if "," in token else "."
        whole, decimal = token.rsplit(separator, 1)
        token = whole + decimal if len(decimal) == 3 else whole + "." + decimal
    try:
        return Decimal(token)
    except InvalidOperation:
        return None


def _normalize_numeric_input(value, control: WebElement) -> str | None:
    number = _plain_decimal(value)
    if number is None:
        return None
    try:
        minimum = _plain_decimal(control.get_attribute("min"))
        maximum = _plain_decimal(control.get_attribute("max"))
        step_value = str(control.get_attribute("step") or "").strip().casefold()
        step = None if step_value in {"", "any"} else _plain_decimal(step_value)
    except Exception:
        return None
    if minimum is not None and number < minimum:
        return None
    if maximum is not None and number > maximum:
        return None
    if step is not None:
        if step <= 0:
            return None
        base = minimum or Decimal("0")
        if (number - base) % step != 0:
            return None
    normalized = format(number, "f")
    if "." in normalized:
        normalized = normalized.rstrip("0").rstrip(".")
    return normalized or "0"


def _browser_numeric_value_is_valid(control: WebElement) -> bool:
    if str(control.get_attribute("aria-invalid") or "").casefold() == "true":
        return False
    try:
        if str(control.get_property("validationMessage") or "").strip():
            return False
    except Exception:
        pass
    try:
        return bool(driver.execute_script(
            "return !arguments[0].checkValidity || arguments[0].checkValidity();",
            control,
        ))
    except Exception:
        return True


def _fill_numeric_control(control: WebElement, value) -> tuple[bool, str]:
    normalized = _normalize_numeric_input(value, control)
    if normalized is None:
        return False, ""
    control.clear()
    control.send_keys(normalized)
    if _browser_numeric_value_is_valid(control):
        return True, normalized
    retry_value = _normalize_numeric_input(
        control.get_attribute("value") or normalized,
        control,
    )
    if retry_value is None:
        return False, normalized
    control.clear()
    control.send_keys(retry_value)
    return _browser_numeric_value_is_valid(control), retry_value


def _unknown_answer(label, field_type, options, question, control, job_title, job_description, text_limit, unresolved_required):
    required = _is_required(question, control)
    key = f"{field_type}:{hash(label)}"
    result = None
    if any(word in label.lower() for word in ("first name", "middle name", "last name", "full name", "email", "phone")):
        answer, reason = None, "contact_field_blocked"
    else:
        result = answer_deterministic_question(label, field_type, options)
        exact_option_unavailable = result.reason_code in {
            "exact_option_unavailable", "exact_option_not_available"
        }
        option_mapping_allowed = (
            required
            and field_type == "select"
            and exact_option_unavailable
            and not is_protected_objective_fact_question(label)
        )
        if (
            not result.can_answer
            and not is_protected_objective_fact_question(label)
            and (not exact_option_unavailable or option_mapping_allowed)
        ):
            result = answer_unknown_question(
                label,
                field_type,
                options,
                job_title,
                job_description or "",
                text_limit,
                required=required,
                constraints=_field_constraints(control),
            )
        answer, reason = (result.answer if result.can_answer else None), result.reason_code
    original_model_answer = str(answer or "").strip()
    numeric_original_answer = ""
    if answer is not None and _is_numeric_control(control, label):
        normalized_answer = _normalize_numeric_input(answer, control)
        if normalized_answer is None:
            answer, reason = None, "numeric_input_invalid"
        elif normalized_answer != str(answer).strip():
            numeric_original_answer = str(answer).strip()
            answer, reason = normalized_answer, "numeric_input_normalized"
    if required and answer is None: unresolved_required.add(key)
    elif answer is not None: unresolved_required.discard(key)
    try:
        control._ai_answer_metadata = {
            "provider_request_count": int(
                getattr(result, "provider_request_count", 0) or 0
            ),
            "original_answer": original_model_answer,
            "reason_code": reason,
        }
    except Exception:
        pass
    queue = globals().get("ai_answer_review_queue")
    if queue is not None:
        try:
            context = globals().get("ai_review_context", {})
            provider_request_count = int(
                getattr(result, "provider_request_count", 0) or 0
            )
            validation_failed = reason in {
                "empty_answer",
                "invalid_confidence",
                "invalid_number",
                "invalid_option",
                "malformed_model_output",
                "multilingual_language_mapping_failed",
                "numeric_input_invalid",
            }
            validation_result = (
                "valid"
                if answer is not None
                else "validation_failed"
                if validation_failed
                else "unresolved_required"
                if required
                else "validation_failed"
            )
            application_outcome = (
                "answer_filled"
                if answer is not None
                else "unresolved_required"
                if required
                else "validation_failed"
            )
            policy_review_required = reason in {
                "ordinary_experience_yes_default",
                "analyst_role_years_minimum_floor",
                "experience_years_minimum_floor",
                "localized_language_exact_fact",
                "language_level_numeric_scale",
                "multilingual_language_numeric_scale",
                "multilingual_language_provider_mapping",
                "numeric_input_normalized",
                "salary_range_accepted_from_expected_salary",
            }
            original_answer = str(
                numeric_original_answer
                or getattr(result, "original_answer", "")
                or ""
            ).strip()
            target_language = str(
                getattr(result, "target_language", "") or ""
            ).strip()
            citizenship_exact_fact = (
                reason == "exact_profile_fact"
                and is_citizenship_question(label)
            )
            if (
                provider_request_count > 0
                or policy_review_required
                or citizenship_exact_fact
            ):
                queue.record_answer(
                    job_id=context.get("job_id", ""),
                    company=context.get("company", ""),
                    job_title=context.get("job_title", job_title),
                    question=label,
                    field_type=field_type,
                    required=required,
                    visible_options=options,
                    proposed_answer=answer,
                    reason_code=reason,
                    provider_request_count=provider_request_count,
                    validation_result=validation_result,
                    application_outcome=application_outcome,
                    conflicts_with_verified_fact=bool(
                        getattr(result, "conflicts_with_verified_fact", False)
                    ),
                    record_without_provider=(
                        policy_review_required or citizenship_exact_fact
                    ),
                    force_high_priority=(
                        reason == "experience_years_minimum_floor"
                        and original_answer in {"", "0"}
                    ),
                    force_normal_priority=citizenship_exact_fact,
                    reviewer_notes=(
                        (
                            f"original_language_fact={original_answer or '[blank]'}; "
                            "scale_detected=1-5"
                        )
                        if reason == "language_level_numeric_scale"
                        else (
                            f"target_language={target_language or '[unknown]'}; "
                            "resolution_path=multilingual_single_field"
                        )
                        if reason in {
                            "multilingual_language_mapping_failed",
                            "multilingual_language_numeric_scale",
                            "multilingual_language_provider_mapping",
                        }
                        else getattr(result, "original_answer", "")
                        if reason == "salary_range_accepted_from_expected_salary"
                        else f"original_proposed_answer={original_answer or '[blank]'}"
                        if reason in {
                            "analyst_role_years_minimum_floor",
                            "experience_years_minimum_floor",
                            "numeric_input_normalized",
                        }
                        else ""
                    ),
                )
            elif required and answer is None and reason != "contact_field_blocked":
                _record_required_review_event(
                    label,
                    field_type,
                    options,
                    reason,
                    validation_result,
                    application_outcome,
                )
        except Exception:
            print_lg("AI answer review queue logging failed; browser workflow continues.")
    target_language = str(
        getattr(result, "target_language", "") or ""
    ).strip()
    if reason in {
        "multilingual_language_mapping_failed",
        "multilingual_language_numeric_scale",
        "multilingual_language_provider_mapping",
    }:
        print_lg(
            "Gemini fallback "
            f"field_type={field_type} language_question_detected=true "
            f"target_language={target_language or 'unknown'} "
            f"option_count={len(options)} path=provider "
            f"reason_code={reason} validation_outcome="
            f"{'valid' if answer is not None else 'unresolved'}"
        )
    else:
        print_lg(f"Gemini fallback field_type={field_type} success={answer is not None} reason_code={reason}")
    return answer


def _answers_match(left, right) -> bool:
    return " ".join(str(left or "").casefold().split()) == " ".join(
        str(right or "").casefold().split()
    )


def _is_select_placeholder(value, control=None) -> bool:
    if control is not None:
        try:
            select = Select(control)
            selected = select.first_selected_option
            selected_value = str(selected.get_attribute("value") or "").strip()
            selected_class = _normalized_form_text(
                selected.get_attribute("class") or ""
            )
            dom_placeholder = any(
                str(selected.get_attribute(name) or "").casefold()
                in {"true", "disabled", "placeholder"}
                for name in (
                    "disabled",
                    "aria-disabled",
                    "data-placeholder",
                    "data-is-placeholder",
                )
            ) or "placeholder" in selected_class
            if dom_placeholder or not selected_value:
                return True
        except Exception:
            pass
        try:
            if _browser_control_is_invalid(control, value, True):
                return True
        except Exception:
            pass
    normalized = _normalized_form_text(value)
    return any(
        _answers_match(value, placeholder)
        for placeholder in (
            "Select an option",
            "Selecciona una opción",
            "Sélectionnez une option",
            "Selectionnez une option",
            "Wybierz opcję",
        )
    ) or (
        "option" in normalized
        and any(
            marker in normalized
            for marker in ("select", "choose", "seleccion", "selection", "wybierz")
        )
    )


def _is_positive_answer(value) -> bool:
    return " ".join(str(value or "").casefold().split()) in {
        "yes",
        "sí",
        "si",
        "oui",
        "ja",
    }


def _is_negative_answer(value) -> bool:
    return _answers_match(value, "No")


def _record_answer_review_event(
    question: str,
    field_type: str,
    visible_options: list[str],
    original_answer: str,
    repaired_answer: str,
    reason_code: str,
    validation_category: str,
    provider_request_count: int = 0,
    validation_result: str = "valid",
    required: bool = True,
    reviewer_notes_extra: str = "",
) -> None:
    queue = globals().get("ai_answer_review_queue")
    if queue is None:
        return
    try:
        context = globals().get("ai_review_context", {})
        is_valid = validation_result in {"valid", "valid_after_repair"}
        citizenship_exact_fact = (
            reason_code == "exact_profile_fact"
            and is_citizenship_question(question)
        )
        notes = (
            f"original_answer={original_answer or '[blank]'}; "
            f"validation_category={validation_category}"
        )
        if reviewer_notes_extra:
            notes += f"; {reviewer_notes_extra}"
        queue.record_answer(
            job_id=context.get("job_id", ""),
            company=context.get("company", ""),
            job_title=context.get("job_title", ""),
            question=question,
            field_type=field_type,
            required=required,
            visible_options=visible_options,
            proposed_answer=repaired_answer,
            reason_code=reason_code,
            provider_request_count=provider_request_count,
            validation_result=validation_result,
            application_outcome=(
                "answer_filled" if is_valid else "validation_failed"
            ),
            record_without_provider=True,
            force_high_priority=not is_valid,
            force_normal_priority=citizenship_exact_fact and is_valid,
            reviewer_notes=notes,
        )
    except Exception:
        print_lg("AI answer review queue logging failed; browser workflow continues.")


def _verified_preserved_answer(
    label: str,
    field_type: str,
    options: list[str],
    current_answer: str,
    constraints: dict | None = None,
):
    if is_experience_capability_question(label):
        # For ordinary capability questions, LinkedIn's confirmed/saved value
        # has first priority. Exact facts and the Yes default apply only when blank.
        return None
    result = answer_verified_question(
        label, field_type, options, constraints
    )
    if result.can_answer:
        return result if not _answers_match(current_answer, result.answer) else None
    if result.reason_code in {
        "exact_option_unavailable", "exact_option_not_available"
    }:
        return result
    return None


def _preserved_override_reason(label: str, current_answer: str, result) -> str:
    if (
        getattr(result, "reason_code", "") == "exact_profile_fact"
        and is_citizenship_question(label)
    ):
        return "exact_profile_fact"
    if getattr(result, "reason_code", "") == "salary_range_accepted_from_expected_salary":
        return "salary_range_accepted_from_expected_salary"
    if getattr(result, "reason_code", "") == "analyst_role_years_minimum_floor":
        return "analyst_role_years_minimum_floor"
    if (
        _is_negative_answer(current_answer)
        and is_experience_capability_question(label)
        and _is_positive_answer(getattr(result, "answer", ""))
    ):
        return "stale_preserved_experience_overridden"
    return "stale_preserved_value_overridden"


def _record_review_outcome(application_outcome: str, reason_code: str = "") -> None:
    queue = globals().get("ai_answer_review_queue")
    if queue is None:
        return
    try:
        context = globals().get("ai_review_context", {})
        queue.record_outcome(
            application_outcome,
            job_id=context.get("job_id", ""),
            company=context.get("company", ""),
            job_title=context.get("job_title", ""),
            reason_code=reason_code,
        )
    except Exception:
        print_lg("AI answer review queue logging failed; browser workflow continues.")


def _record_required_review_event(
    question: str,
    field_type: str,
    visible_options: list[str],
    reason_code: str,
    validation_result: str = "unresolved_required",
    application_outcome: str = "unresolved_required",
) -> None:
    queue = globals().get("ai_answer_review_queue")
    if queue is None:
        return
    try:
        context = globals().get("ai_review_context", {})
        queue.record_required_event(
            job_id=context.get("job_id", ""),
            company=context.get("company", ""),
            job_title=context.get("job_title", ""),
            question=question,
            field_type=field_type,
            visible_options=visible_options,
            reason_code=reason_code,
            validation_result=validation_result,
            application_outcome=application_outcome,
        )
    except Exception:
        print_lg("AI answer review queue logging failed; browser workflow continues.")


def _is_overall_experience_question(label: str) -> bool:
    label = re.sub(r"[^\wáéíóúüñ]+", " ", label.casefold()).strip()
    patterns = (
        r"(?:how many )?(?:total |overall )?years of (?:professional |work )?experience(?: do you have)?",
        r"(?:total|overall) (?:professional|work) experience",
        r"total years working professionally",
        r"(?:cuántos )?años (?:totales )?de experiencia(?: profesional)?(?: tienes)?",
        r"experiencia profesional total",
    )
    return any(re.fullmatch(pattern, label) for pattern in patterns)


def _browser_control_is_invalid(
    control: WebElement,
    current_value,
    required: bool,
) -> bool:
    if str(control.get_attribute("aria-invalid") or "").casefold() == "true":
        return True
    message, validity = _validation_details(control)
    if message or validity.get("valid") is False:
        return True
    if any(
        bool(validity.get(flag))
        for flag in (
            "badInput",
            "typeMismatch",
            "rangeUnderflow",
            "rangeOverflow",
            "stepMismatch",
            "valueMissing",
        )
    ):
        return True
    if required and not current_value:
        return True
    try:
        return not bool(driver.execute_script(
            "return !arguments[0].checkValidity || arguments[0].checkValidity();",
            control,
        ))
    except Exception:
        return False


def _question_label(question: WebElement, container: WebElement | None = None) -> str:
    target = container or question
    label = try_xp(
        target,
        './/span[@data-test-form-builder-radio-button-form-component__title]',
        False,
    )
    if not label:
        label = try_xp(question, ".//label[@for]", False)
    if not label:
        try:
            label = question.find_element(By.TAG_NAME, "label")
            try:
                label = label.find_element(By.TAG_NAME, "span")
            except Exception:
                pass
        except Exception:
            label = None
    return str(getattr(label, "text", "") or "Unknown")


def _linkedin_validation_message(question: WebElement) -> str:
    messages = []
    validation_xpath = (
        './/*[contains(@class,"artdeco-inline-feedback__message") '
        'or contains(@class,"artdeco-inline-feedback") '
        'or contains(@data-test,"error-message") '
        'or @role="alert"]'
    )
    try:
        elements = question.find_elements(By.XPATH, validation_xpath)
    except Exception:
        elements = []
    for element in elements:
        try:
            if hasattr(element, "is_displayed") and not element.is_displayed():
                continue
            message = str(getattr(element, "text", "") or "").strip()
            if message and message not in messages:
                messages.append(message)
        except Exception:
            continue
    return " | ".join(messages)


def _collect_invalid_required_fields(modal: WebElement) -> list[dict]:
    invalid_fields = []
    for question in modal.find_elements(By.XPATH, ".//div[@data-test-form-element]"):
        linkedin_message = _linkedin_validation_message(question)
        select_control = try_xp(question, ".//select", False)
        if select_control:
            select = Select(select_control)
            options = [option.text for option in select.options]
            current = select.first_selected_option.text
            required = _is_required(question, select_control)
            placeholder = _is_select_placeholder(current, select_control)
            invalid = _browser_control_is_invalid(
                select_control, "" if placeholder else current, required
            )
            if invalid or linkedin_message:
                invalid_fields.append({
                    "question": question,
                    "control": select_control,
                    "kind": "select",
                    "label": _question_label(question),
                    "options": options,
                    "current": current,
                    "validation_message": linkedin_message,
                    "constraints": {
                        name: select_control.get_attribute(name)
                        for name in ("required", "aria-required")
                    },
                    "validation_category": _validation_category(select_control),
                })
            continue

        radio = try_xp(
            question,
            './/fieldset[@data-test-form-builder-radio-button-form-component="true"]',
            False,
        )
        if radio:
            controls = radio.find_elements(By.TAG_NAME, "input")
            options = []
            current = ""
            for control in controls:
                option_id = control.get_attribute("id")
                option_label = try_xp(
                    radio, f'.//label[@for="{option_id}"]', False
                )
                option_text = str(getattr(option_label, "text", "") or "Unknown")
                options.append(option_text)
                if control.is_selected():
                    current = option_text
            required = _is_required(question, radio)
            invalid = _browser_control_is_invalid(radio, current, required)
            if invalid or linkedin_message:
                invalid_fields.append({
                    "question": question,
                    "control": radio,
                    "controls": controls,
                    "kind": "radio",
                    "label": _question_label(question, radio),
                    "options": options,
                    "current": current,
                    "validation_message": linkedin_message,
                    "constraints": {
                        name: radio.get_attribute(name)
                        for name in ("required", "aria-required")
                    },
                    "validation_category": _validation_category(radio),
                })
            continue

        control = try_xp(
            question, ".//input[@type='text' or @type='number']", False
        )
        kind = "text"
        if not control:
            control = try_xp(question, ".//textarea", False)
            kind = "textarea"
        if control:
            label = _question_label(question)
            current = str(control.get_attribute("value") or "")
            required = _is_required(question, control)
            field_type = (
                "number" if kind == "text" and _is_numeric_control(control, label)
                else kind
            )
            invalid = _browser_control_is_invalid(control, current, required)
            if invalid or linkedin_message:
                invalid_fields.append({
                    "question": question,
                    "control": control,
                    "kind": field_type,
                    "label": label,
                    "options": [],
                    "current": current,
                    "validation_message": linkedin_message,
                    "constraints": {
                        name: control.get_attribute(name)
                        for name in (
                            "type",
                            "inputmode",
                            "min",
                            "max",
                            "step",
                            "maxlength",
                            "required",
                            "aria-required",
                        )
                    },
                    "validation_category": _validation_category(control),
                })
            continue

        checkbox = try_xp(question, ".//input[@type='checkbox']", False)
        if checkbox and (
            (_is_required(question, checkbox) and not checkbox.is_selected())
            or linkedin_message
        ):
            invalid_fields.append({
                "question": question,
                "control": checkbox,
                "kind": "checkbox",
                "label": _question_label(question),
                "options": [],
                "current": "",
                "validation_message": linkedin_message,
                "constraints": {"required": checkbox.get_attribute("required")},
                "validation_category": "required_value_missing",
            })
    return invalid_fields


def _form_page_signature(modal: WebElement) -> tuple:
    signature = []
    for question in modal.find_elements(By.XPATH, ".//div[@data-test-form-element]"):
        kind = "unknown"
        control = try_xp(question, ".//select", False)
        if control:
            kind = "select"
        else:
            control = try_xp(
                question,
                './/fieldset[@data-test-form-builder-radio-button-form-component="true"]',
                False,
            )
            if control:
                kind = "radio"
            else:
                control = try_xp(
                    question, ".//input[@type='text' or @type='number']", False
                )
                if control:
                    kind = (
                        "number"
                        if _is_numeric_control(control, _question_label(question))
                        else "text"
                    )
                else:
                    control = try_xp(question, ".//textarea", False)
                    if control:
                        kind = "textarea"
                    else:
                        control = try_xp(
                            question, ".//input[@type='checkbox']", False
                        )
                        if control:
                            kind = "checkbox"
        try:
            control_id = str(control.get_attribute("id") or "") if control else ""
        except Exception:
            control_id = ""
        signature.append((kind, _question_label(question), control_id))
    return tuple(signature)


def _fill_repair_field(field: dict, answer: str) -> bool:
    control = field["control"]
    kind = field["kind"]
    if kind == "number":
        valid, _submitted = _fill_numeric_control(control, answer)
        return valid
    for _attempt in range(2):
        try:
            if kind == "select":
                Select(control).select_by_visible_text(answer)
            elif kind == "radio":
                index = field["options"].index(answer)
                actions.move_to_element(field["controls"][index]).click().perform()
            elif kind in {"text", "textarea"}:
                control.clear()
                control.send_keys(answer)
            elif kind == "checkbox":
                actions.move_to_element(control).click().perform()
            else:
                return False
        except Exception:
            continue
        current = (
            Select(control).first_selected_option.text
            if kind == "select"
            else answer
        )
        if not _browser_control_is_invalid(control, current, True):
            return True
    return False


def repair_invalid_required_fields(
    modal: WebElement,
    work_location: str,
    job_title: str,
    job_description: str,
    unresolved_required: set,
    repaired_page_signatures: set,
    invalid_fields: list[dict] | None = None,
) -> bool:
    """Repair each invalid required field once, with at most one pass per page."""
    if invalid_fields is None:
        invalid_fields = _collect_invalid_required_fields(modal)
    if not invalid_fields:
        return False
    signature = tuple(
        sorted((field["kind"], field["label"]) for field in invalid_fields)
    )
    if signature in repaired_page_signatures:
        return False
    repaired_page_signatures.add(signature)
    all_valid = True
    for field in invalid_fields:
        label = field["label"]
        kind = field["kind"]
        options = field["options"]
        current = field["current"]
        key = f"{kind}:{hash(label)}"
        result = None
        answer = None
        reason = "deterministic_invalid_field_repair"
        metadata = getattr(field["control"], "_ai_answer_metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}

        if _is_resume_attachment_question(label):
            positive_option = _localized_positive_option(options)
            if (
                _resume_selected_in_modal(modal)
                and positive_option is not None
                and _fill_repair_field(field, positive_option)
            ):
                unresolved_required.discard(key)
                _record_answer_review_event(
                    label,
                    kind,
                    options,
                    current,
                    positive_option,
                    "resume_attachment_confirmed",
                    field["validation_category"],
                    0,
                    "valid",
                )
            else:
                all_valid = False
                unresolved_required.add(key)
            continue

        if kind == "checkbox":
            answer = "checked"
        elif kind == "number" and current:
            answer = _normalize_numeric_input(current, field["control"])
            if answer is not None and answer != current.strip():
                reason = "numeric_input_normalized"
        if not answer:
            result = answer_verified_question(
                label, kind, options, field["constraints"]
            )
            if result.can_answer:
                answer = result.answer
                if result.reason_code in {
                    "analyst_role_years_minimum_floor",
                    "language_level_numeric_scale",
                    "localized_language_exact_fact",
                }:
                    reason = result.reason_code
            else:
                exact_option_unavailable = result.reason_code in {
                    "exact_option_unavailable", "exact_option_not_available"
                }
                option_mapping_allowed = (
                    kind == "select"
                    and exact_option_unavailable
                    and not is_protected_objective_fact_question(label)
                )
            if (
                not answer
                and not is_protected_objective_fact_question(label)
                and (not exact_option_unavailable or option_mapping_allowed)
            ):
                result = answer_unknown_question(
                    label,
                    kind,
                    options,
                    job_title,
                    job_description or "",
                    None,
                    required=True,
                    constraints={
                        **field["constraints"],
                        "validation_message": field.get(
                            "validation_message", ""
                        ),
                    },
                )
                if result.can_answer:
                    answer = result.answer
                    reason = (
                        result.reason_code
                        if result.reason_code in {
                            "multilingual_language_numeric_scale",
                            "multilingual_language_provider_mapping",
                        }
                        else "provider_invalid_field_repair"
                        if int(result.provider_request_count or 0) > 0
                        else "deterministic_invalid_field_repair"
                    )
        provider_count = int(
            getattr(result, "provider_request_count", 0)
            or metadata.get("provider_request_count", 0)
            or 0
        )
        valid = bool(answer) and _fill_repair_field(field, str(answer))
        if valid:
            unresolved_required.discard(key)
            original = str(
                getattr(result, "original_answer", "") or current or ""
            )
            _record_answer_review_event(
                label,
                kind,
                options,
                original,
                str(answer),
                reason,
                field["validation_category"],
                provider_count,
                (
                    "valid_after_repair"
                    if reason == "numeric_input_normalized"
                    else "valid"
                ),
                reviewer_notes_extra=(
                    f"target_language={getattr(result, 'target_language', '') or '[unknown]'}"
                    if reason in {
                        "multilingual_language_numeric_scale",
                        "multilingual_language_provider_mapping",
                    }
                    else ""
                ),
            )
        else:
            all_valid = False
            unresolved_required.add(key)
            _record_answer_review_event(
                label,
                kind,
                options,
                current,
                str(answer or ""),
                "invalid_field_repair_failed",
                field["validation_category"],
                provider_count,
                "validation_failed",
            )
    return all_valid and not unresolved_required


def _repair_after_failed_advance(
    modal: WebElement,
    before_signature: tuple,
    work_location: str,
    job_title: str,
    job_description: str,
    unresolved_required: set,
    repaired_page_signatures: set,
) -> bool | None:
    """Repair only when an original Next/Review click left this page in place."""
    if _form_page_signature(modal) != before_signature:
        return None
    invalid_fields = _collect_invalid_required_fields(modal)
    if not invalid_fields:
        return None
    return repair_invalid_required_fields(
        modal,
        work_location,
        job_title,
        job_description,
        unresolved_required,
        repaired_page_signatures,
        invalid_fields,
    )


# Function to answer the questions for Easy Apply
def answer_questions(modal: WebElement, questions_list: set, work_location: str, job_title: str, unresolved_required: set, job_description: str | None = None ) -> set:

    # Get all questions from the page
     
    all_questions = modal.find_elements(By.XPATH, ".//div[@data-test-form-element]")
    # all_questions = modal.find_elements(By.CLASS_NAME, "jobs-easy-apply-form-element")
    # all_list_questions = modal.find_elements(By.XPATH, ".//div[@data-test-text-entity-list-form-component]")
    # all_single_line_questions = modal.find_elements(By.XPATH, ".//div[@data-test-single-line-text-form-component]")
    # all_questions = all_questions + all_list_questions + all_single_line_questions

    for Question in all_questions:
        # Check if it's a select Question
        select = try_xp(Question, ".//select", False)
        if select:
            label_org = "Unknown"
            try:
                label = Question.find_element(By.TAG_NAME, "label")
                label_org = label.find_element(By.TAG_NAME, "span").text
            except: pass
            answer = 'Yes'
            matched_rule = False
            label = label_org.lower()

            select_element = select
            select = Select(select_element)
            selected_option = select.first_selected_option.text
            optionsText = []
            options = '"List of phone country codes"'
            if label != "phone country code":
                optionsText = [option.text for option in select.options]
                options = "".join([f' "{option}",' for option in optionsText])
            prev_answer = selected_option

            if _is_resume_attachment_question(label_org):
                required = _is_required(Question, select_element)
                positive_option = _localized_positive_option(optionsText)
                resume_selected = _resume_selected_in_modal(modal)
                if resume_selected and positive_option is not None:
                    select.select_by_visible_text(positive_option)
                    answer = positive_option
                    unresolved_required.discard(f"select:{hash(label_org)}")
                    _record_answer_review_event(
                        label_org,
                        "select",
                        optionsText,
                        selected_option,
                        answer,
                        "resume_attachment_confirmed",
                        "selected_resume_ui_evidence",
                        required=required,
                    )
                else:
                    answer = None
                    if required:
                        unresolved_required.add(f"select:{hash(label_org)}")
                        _record_required_review_event(
                            label_org,
                            "select",
                            optionsText,
                            (
                                "resume_attachment_not_confirmed"
                                if not resume_selected
                                else "resume_attachment_positive_option_unavailable"
                            ),
                        )
                questions_list.add((
                    "select",
                    "answered" if answer else "unresolved",
                    "resume_attachment_confirmation",
                ))
                continue

            placeholder_selected = _is_select_placeholder(
                selected_option, select_element
            )
            if not overwrite_previous_answers and not placeholder_selected:
                exact = _verified_preserved_answer(
                    label_org,
                    "select",
                    optionsText,
                    selected_option,
                    _field_constraints(select_element),
                )
                if exact is not None and exact.can_answer:
                    select.select_by_visible_text(exact.answer)
                    answer = exact.answer
                    _record_answer_review_event(
                        label_org,
                        "select",
                        optionsText,
                        selected_option,
                        answer,
                        _preserved_override_reason(
                            label_org, selected_option, exact
                        ),
                        "verified_fact_conflict",
                        required=_is_required(Question, select_element),
                        reviewer_notes_extra=(
                            getattr(exact, "original_answer", "")
                            if getattr(exact, "reason_code", "")
                            == "salary_range_accepted_from_expected_salary"
                            else ""
                        ),
                    )
                elif exact is not None:
                    answer = None
                    if _is_required(Question, select_element):
                        unresolved_required.add(f"select:{hash(label_org)}")
                        _record_required_review_event(
                            label_org,
                            "select",
                            optionsText,
                            getattr(
                                exact,
                                "reason_code",
                                "exact_option_unavailable",
                            ),
                        )
                else:
                    answer = selected_option
            else:
                if 'email' in label or 'phone' in label: answer = prev_answer; matched_rule = True
                elif 'gender' in label or 'sex' in label: answer = gender; matched_rule = True
                elif 'disability' in label: answer = disability_status; matched_rule = True
                elif any(language in label for language in (
                    'english', 'inglés', 'ingles', 'anglais',
                    'spanish', 'español', 'espanol', 'castellano', 'espagnol',
                    'catalan', 'catalán', 'català', 'catala',
                    'french', 'français', 'francais',
                )):
                    pass
                elif 'proficiency' in label: answer = (
                    'Nativo o bilingüe' if 'Nativo o bilingüe' in optionsText
                    else ('Native or bilingual' if 'Native or bilingual' in optionsText 
                          else 'Professional')
                ); matched_rule = True
                #english level 
                elif 'nivel' in label and 'ingl' in label: answer = 'Nativo o bilingüe' if 'Nativo o bilingüe' in optionsText else 'Native or bilingual'; matched_rule = True
                foundOption = False
                if matched_rule:
                    try:
                        select.select_by_visible_text(answer)
                        foundOption = True
                    except NoSuchElementException:
                        pass
                if matched_rule and not foundOption:
                    possible_answer_phrases = ["Decline", "not wish", "don't wish", "Prefer not", "not want"] if answer == 'Decline' else [answer]
                    for phrase in possible_answer_phrases:
                        for option in optionsText:
                            if phrase in option:
                                select.select_by_visible_text(option)
                                answer = f'Decline ({option})' if len(possible_answer_phrases) > 1 else option
                                foundOption = True
                                break
                        if foundOption: break
                if not foundOption:
                    optionsText = [option.text for option in select.options]
                    answer = _unknown_answer(label_org, "select", optionsText, Question, select_element, job_title, job_description, None, unresolved_required)
                    if answer is not None:
                        try:
                            select.select_by_visible_text(answer)
                            selected_answer = select.first_selected_option.text
                            if _is_select_placeholder(
                                selected_answer, select_element
                            ):
                                answer = None
                            else:
                                answer = selected_answer
                        except NoSuchElementException:
                            answer = None
                    if answer is None:
                        if _is_required(Question, select_element):
                            unresolved_required.add(
                                f"select:{hash(label_org)}"
                            )
                        answer = prev_answer
                    else:
                        unresolved_required.discard(
                            f"select:{hash(label_org)}"
                        )
            questions_list.add(("select", "answered" if answer else "unresolved", "preserved" if prev_answer else "new"))
            continue
        
        # Check if it's a radio Question
        radio = try_xp(Question, './/fieldset[@data-test-form-builder-radio-button-form-component="true"]', False)
        if radio:
            prev_answer = None
            label = try_xp(radio, './/span[@data-test-form-builder-radio-button-form-component__title]', False)
            try: label = find_by_class(label, "visually-hidden", 2.0)
            except: pass
            label_org = label.text if label else "Unknown"
            answer = 'Yes'
            matched_rule = False
            label = label_org.lower()

            options = radio.find_elements(By.TAG_NAME, 'input')
            options_labels = []
            visible_options = []
            
            for option in options:
                id = option.get_attribute("id")
                option_label = try_xp(radio, f'.//label[@for="{id}"]', False)
                visible_options.append(option_label.text if option_label else "Unknown")
                options_labels.append( f'"{option_label.text if option_label else "Unknown"}"<{option.get_attribute("value")}>' ) # Saving option as "label <value>"
                if option.is_selected(): prev_answer = visible_options[-1]

            if _is_resume_attachment_question(label_org):
                required = _is_required(Question, radio)
                positive_option = _localized_positive_option(visible_options)
                resume_selected = _resume_selected_in_modal(modal)
                if resume_selected and positive_option is not None:
                    target = options[visible_options.index(positive_option)]
                    actions.move_to_element(target).click().perform()
                    answer = positive_option
                    unresolved_required.discard(f"radio:{hash(label_org)}")
                    _record_answer_review_event(
                        label_org,
                        "radio",
                        visible_options,
                        prev_answer or "",
                        answer,
                        "resume_attachment_confirmed",
                        "selected_resume_ui_evidence",
                        required=required,
                    )
                else:
                    answer = None
                    if required:
                        unresolved_required.add(f"radio:{hash(label_org)}")
                        _record_required_review_event(
                            label_org,
                            "radio",
                            visible_options,
                            (
                                "resume_attachment_not_confirmed"
                                if not resume_selected
                                else "resume_attachment_positive_option_unavailable"
                            ),
                        )
                questions_list.add((
                    "radio",
                    "answered" if answer else "unresolved",
                    "resume_attachment_confirmation",
                ))
                continue

            if not overwrite_previous_answers and prev_answer is not None:
                exact = _verified_preserved_answer(
                    label_org,
                    "radio",
                    visible_options,
                    prev_answer,
                    _field_constraints(radio),
                )
                if exact is not None and exact.can_answer:
                    target = options[visible_options.index(exact.answer)]
                    actions.move_to_element(target).click().perform()
                    answer = exact.answer
                    _record_answer_review_event(
                        label_org,
                        "radio",
                        visible_options,
                        prev_answer,
                        answer,
                        _preserved_override_reason(
                            label_org, prev_answer, exact
                        ),
                        "verified_fact_conflict",
                        required=_is_required(Question, radio),
                        reviewer_notes_extra=(
                            getattr(exact, "original_answer", "")
                            if getattr(exact, "reason_code", "")
                            == "salary_range_accepted_from_expected_salary"
                            else ""
                        ),
                    )
                elif exact is not None:
                    answer = None
                    if _is_required(Question, radio):
                        unresolved_required.add(f"radio:{hash(label_org)}")
                        _record_required_review_event(
                            label_org,
                            "radio",
                            visible_options,
                            getattr(
                                exact,
                                "reason_code",
                                "exact_option_unavailable",
                            ),
                        )
                else:
                    answer = prev_answer
            else:
                if 'citizenship' in label: pass
                elif 'veteran' in label or 'protected' in label: answer = veteran_status; matched_rule = True
                elif 'disability' in label or 'handicapped' in label: 
                    answer = disability_status; matched_rule = True
                foundOption = try_xp(radio, f".//label[normalize-space()='{answer}']", False) if matched_rule else False
                if foundOption:
                    actions.move_to_element(foundOption).click().perform()
                else:
                    possible_answer_phrases = ["Decline", "not wish", "don't wish", "Prefer not", "not want"] if answer == 'Decline' else [answer]
                    ele = None
                    if matched_rule:
                        for phrase in possible_answer_phrases:
                            for i, option_label in enumerate(options_labels):
                                if phrase in option_label:
                                    foundOption = options[i]
                                    ele = foundOption
                                    answer = f'Decline ({option_label})' if len(possible_answer_phrases) > 1 else option_label
                                    break
                            if foundOption: break
                    # if answer == 'Decline':
                    #     answer = options_labels[0]
                    #     for phrase in ["Prefer not", "not want", "not wish"]:
                    #         foundOption = try_xp(radio, f".//label[normalize-space()='{phrase}']", False)
                    #         if foundOption:
                    #             answer = f'Decline ({phrase})'
                    #             ele = foundOption
                    #             break
                    if ele is None:
                        answer = _unknown_answer(label_org, "radio", visible_options, Question, radio, job_title, job_description, None, unresolved_required)
                        if answer is not None: ele = options[visible_options.index(answer)]
                    if ele is not None: actions.move_to_element(ele).click().perform()
            questions_list.add(("radio", "answered" if answer else "unresolved", "preserved" if prev_answer else "new"))
            continue
        
        # Check if it's a text question
        text = try_xp(Question, ".//input[@type='text' or @type='number']", False)
        if text: 
            do_actions = False
            label = try_xp(Question, ".//label[@for]", False)
            try: label = label.find_element(By.CLASS_NAME,'visually-hidden')
            except: pass
            label_org = label.text if label else "Unknown"
            answer = "" # years_of_experience
            label = label_org.lower()
            field_type = "number" if (
                _is_numeric_control(text, label_org)
                or re.search(r"\b(how many|years?|cuántos|cuantos|años?)\b", label)
            ) else "text"

            prev_answer = text.get_attribute("value")
            preserved_answer = prev_answer
            preserved_exact = None
            exact_option_blocked = False
            if prev_answer and not overwrite_previous_answers:
                preserved_exact = _verified_preserved_answer(
                    label_org,
                    field_type,
                    [],
                    prev_answer,
                    _field_constraints(text),
                )
                if preserved_exact is not None and preserved_exact.can_answer:
                    answer = preserved_exact.answer
                elif preserved_exact is not None:
                    exact_option_blocked = True
                    if _is_required(Question, text):
                        unresolved_required.add(f"{field_type}:{hash(label_org)}")
                        _record_required_review_event(
                            label_org,
                            field_type,
                            [],
                            getattr(
                                preserved_exact,
                                "reason_code",
                                "exact_option_unavailable",
                            ),
                        )
            if (not prev_answer or overwrite_previous_answers or answer) and not exact_option_blocked:
                if answer: pass
                elif _is_overall_experience_question(label): answer = years_of_experience
                #yes/no exp
                #############################################################
                ##############################################################################
                elif 'earliest' in label or 'date' in label: answer = earliest_start_date
                elif 'phone' in label or 'mobile' in label: answer = phone_number
                elif 'street' in label: answer = street
                elif 'city' in label or 'location' in label or 'address' in label:
                    answer = current_city if current_city else work_location
                    do_actions = True
                elif 'signature' in label: answer = full_name # 'signature' in label or 'legal name' in label or 'your name' in label or 'full name' in label: answer = full_name     # What if question is 'name of the city or university you attend, name of referral etc?'
                elif 'name' in label:
                    if 'full' in label: answer = full_name
                    elif 'first' in label and 'last' not in label: answer = first_name
                    elif 'middle' in label and 'last' not in label: answer = middle_name
                    elif 'last' in label and 'first' not in label: answer = last_name
                    elif 'employer' in label: answer = recent_employer
                    else: answer = full_name
                elif 'notice' in label:
                    if 'month' in label:
                        answer = notice_period_months
                    elif 'week' in label:
                        answer = notice_period_weeks
                    else: answer = notice_period
                    #expected salary.      
                elif 'salary' in label or 'compensation' in label or 'ctc' in label or 'pay' in label or 'expectativas' in label or 'salariales' in label or 'salarial' in label: 
                    if 'current' in label or 'present' in label:
                        if 'month' in label:
                            answer = current_ctc_monthly
                        elif 'lakh' in label:
                            answer = current_ctc_lakhs
                        else:
                            answer = current_ctc
                    else:
                        answer = _unknown_answer(
                            label_org,
                            field_type,
                            [],
                            Question,
                            text,
                            job_title,
                            job_description,
                            None,
                            unresolved_required,
                        ) or ""
                elif 'linkedin' in label: answer = linkedIn
                elif 'website' in label or 'blog' in label or 'portfolio' in label or 'link' in label: answer = website
                elif 'scale of 1-10' in label: answer = confidence_level
                elif 'headline' in label: answer = linkedin_headline
                elif ('hear' in label or 'come across' in label) and 'this' in label and ('job' in label or 'position' in label): answer = "https://github.com/GodsScion/Auto_job_applier_linkedIn"
                elif 'state' in label or 'province' in label: answer = state
                elif 'zip' in label or 'postal' in label or 'code' in label: answer = zipcode
                elif 'country' in label: answer = country
                else: answer = answer_common_questions(label,answer)
                ##> ------ Dheeraj Deshwal : dheeraj9811 Email:dheeraj20194@iiitd.ac.in/dheerajdeshwal9811@gmail.com - Feature ------

                if answer == "":
                    try: text_limit = int(text.get_attribute("maxlength") or 0) or None
                    except (TypeError, ValueError): text_limit = None
                    answer = _unknown_answer(label_org, field_type, [], Question, text, job_title, job_description, text_limit, unresolved_required) or ""
                 ##< 
                if answer:
                    if _is_numeric_control(text, label_org):
                        valid_numeric, submitted_numeric = _fill_numeric_control(
                            text, answer
                        )
                        if valid_numeric:
                            answer = submitted_numeric
                            unresolved_required.discard(
                                f"{field_type}:{hash(label_org)}"
                            )
                        else:
                            answer = ""
                            if _is_required(Question, text):
                                unresolved_required.add(
                                    f"{field_type}:{hash(label_org)}"
                                )
                                _record_required_review_event(
                                    label_org,
                                    field_type,
                                    [],
                                    "numeric_browser_validation_failed",
                                    "validation_failed",
                                    "validation_failed",
                                )
                    else:
                        text.clear()
                        text.send_keys(answer)
                    if answer and preserved_exact is not None and preserved_exact.can_answer:
                        _record_answer_review_event(
                            label_org,
                            field_type,
                            [],
                            preserved_answer,
                            answer,
                            _preserved_override_reason(
                                label_org, preserved_answer, preserved_exact
                            ),
                            "verified_fact_conflict",
                            required=_is_required(Question, text),
                            reviewer_notes_extra=(
                                getattr(preserved_exact, "original_answer", "")
                                if getattr(preserved_exact, "reason_code", "")
                                == "salary_range_accepted_from_expected_salary"
                                else ""
                            ),
                        )
                if do_actions:
                    sleep(2)
                    actions.send_keys(Keys.ARROW_DOWN)
                    actions.send_keys(Keys.ENTER).perform()
            questions_list.add((field_type, "answered" if text.get_attribute("value") else "unresolved", "preserved" if preserved_answer else "new"))
            continue

        # Check if it's a textarea question
        text_area = try_xp(Question, ".//textarea", False)
        if text_area:
            label = try_xp(Question, ".//label[@for]", False)
            label_org = label.text if label else "Unknown"
            label = label_org.lower()
            answer = ""
            prev_answer = text_area.get_attribute("value")
            if not prev_answer or overwrite_previous_answers:
                if 'summary' in label: answer = linkedin_summary
                elif 'cover' in label: answer = cover_letter
                if answer == "":
                    try: text_limit = int(text_area.get_attribute("maxlength") or 0) or None
                    except (TypeError, ValueError): text_limit = None
                    answer = _unknown_answer(label_org, "textarea", [], Question, text_area, job_title, job_description, text_limit, unresolved_required) or ""
            if answer:
                text_area.clear()
                text_area.send_keys(answer)
            questions_list.add(("textarea", "answered" if text_area.get_attribute("value") else "unresolved", "preserved" if prev_answer else "new"))
            ##<
            continue

        # Check if it's a checkbox question
        checkbox = try_xp(Question, ".//input[@type='checkbox']", False)
        if checkbox:
            label = try_xp(Question, ".//span[@class='visually-hidden']", False)
            label_org = label.text if label else "Unknown"
            label = label_org.lower()
            answer = try_xp(Question, ".//label[@for]", False)  # Sometimes multiple checkboxes are given for 1 question, Not accounted for that yet
            answer = answer.text if answer else "Unknown"
            prev_answer = checkbox.is_selected()
            checked = prev_answer
            if not prev_answer and _is_required(Question, checkbox):
                try:
                    actions.move_to_element(checkbox).click().perform()
                    checked = True
                except Exception as e: 
                    print_lg("Checkbox click failed!", e)
                    _record_required_review_event(
                        label_org,
                        "checkbox",
                        [answer],
                        "checkbox_click_failed",
                        "validation_failed",
                        "validation_failed",
                    )
                    pass
            questions_list.add(("checkbox", "answered" if checked else "optional_unchecked", "preserved" if prev_answer else "new"))
            continue


    # Select todays date
    try_xp(driver, "//button[contains(@aria-label, 'This is today')]")

    # Collect important skills
    # if 'do you have' in label and 'experience' in label and ' in ' in label -> Get word (skill) after ' in ' from label
    # if 'how many years of experience do you have in ' in label -> Get word (skill) after ' in '

    return questions_list




def external_apply(pagination_element: WebElement, job_id: str, job_link: str, resume: str, date_listed, application_link: str, screenshot_name: str) -> tuple[bool, str, int]:
    '''
    Function to open new tab and save external job application links
    '''
    global tabs_count, dailyEasyApplyLimitReached
    if easy_apply_only:
        try:
            if "exceeded the daily application limit" in driver.find_element(By.CLASS_NAME, "artdeco-inline-feedback__message").text: dailyEasyApplyLimitReached = True
        except: pass
        print_lg("Easy apply failed I guess!")
        if pagination_element != None: return True, application_link, tabs_count
    try:
        wait.until(EC.element_to_be_clickable((By.XPATH, ".//button[contains(@class,'jobs-apply-button') and contains(@class, 'artdeco-button--3')]"))).click() # './/button[contains(span, "Apply") and not(span[contains(@class, "disabled")])]'
        wait_span_click(driver, "Continue", 1, True, False)
        windows = driver.window_handles
        tabs_count = len(windows)
        driver.switch_to.window(windows[-1])
        application_link = driver.current_url
        print_lg('Got the external application link "{}"'.format(application_link))
        if close_tabs and driver.current_window_handle != linkedIn_tab: driver.close()
        driver.switch_to.window(linkedIn_tab)
        return False, application_link, tabs_count
    except Exception as e:
        # print_lg(e)
        print_lg("Failed to apply!")
        failed_job(job_id, job_link, resume, date_listed, "Probably didn't find Apply button or unable to switch tabs.", e, application_link, screenshot_name)
        global failed_count
        failed_count += 1
        return True, application_link, tabs_count



def follow_company(modal: WebDriver = driver) -> None:
    '''
    Function to follow or un-follow easy applied companies based om `follow_companies`
    '''
    try:
        follow_checkbox_input = try_xp(modal, ".//input[@id='follow-company-checkbox' and @type='checkbox']", False)
        if follow_checkbox_input and follow_checkbox_input.is_selected() != follow_companies:
            try_xp(modal, ".//label[@for='follow-company-checkbox']")
    except Exception as e:
        print_lg("Failed to update follow companies checkbox!", e)
    


#< Failed attempts logging
def failed_job(job_id: str, job_link: str, resume: str, date_listed, error: str, exception: Exception, application_link: str, screenshot_name: str) -> None:
    '''
    Function to update failed jobs list in excel
    '''
    try:
        with open(failed_file_name, 'a', newline='', encoding='utf-8') as file:
            fieldnames = ['Job ID', 'Job Link', 'Resume Tried', 'Date listed', 'Date Tried', 'Assumed Reason', 'Stack Trace', 'External Job link', 'Screenshot Name']
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            if file.tell() == 0: writer.writeheader()
            writer.writerow({'Job ID':job_id, 'Job Link':job_link, 'Resume Tried':resume, 'Date listed':date_listed, 'Date Tried':datetime.now(), 'Assumed Reason':error, 'Stack Trace':exception, 'External Job link':application_link, 'Screenshot Name':screenshot_name})
            file.close()
    except Exception as e:
        print_lg("Failed to update failed jobs list!", e)
        pyautogui.alert("Failed to update the excel of failed jobs!\nProbably because of 1 of the following reasons:\n1. The file is currently open or in use by another program\n2. Permission denied to write to the file\n3. Failed to find the file", "Failed Logging")


def screenshot(driver: WebDriver, job_id: str, failedAt: str) -> str:
    '''
    Function to to take screenshot for debugging
    - Returns screenshot name as String
    '''
    screenshot_name = "{} - {} - {}.png".format( job_id, failedAt, str(datetime.now()) )
    path = logs_folder_path+"/screenshots/"+screenshot_name.replace(":",".")
    # special_chars = {'*', '"', '\\', '<', '>', ':', '|', '?'}
    # for char in special_chars:  path = path.replace(char, '-')
    driver.save_screenshot(path.replace("//","/"))
    return screenshot_name
#>



def submitted_jobs(job_id: str, title: str, company: str, work_location: str, work_style: str, description: str, experience_required: int | Literal['Unknown', 'Error in extraction'], 
                   skills: list[str] | Literal['In Development'], hr_name: str | Literal['Unknown'], hr_link: str | Literal['Unknown'], resume: str, 
                   reposted: bool, date_listed: datetime | Literal['Unknown'], date_applied:  datetime | Literal['Pending'], job_link: str, application_link: str, 
                   questions_list: set | None, connect_request: Literal['In Development']) -> None:
    '''
    Function to create or update the Applied jobs CSV file, once the application is submitted successfully
    '''
    try:
        with open(file_name, mode='a', newline='', encoding='utf-8') as csv_file:
            fieldnames = ['Job ID', 'Title', 'Company', 'Work Location', 'Work Style', 'About Job', 'Experience required', 'Skills required', 'HR Name', 'HR Link', 'Resume', 'Re-posted', 'Date Posted', 'Date Applied', 'Job Link', 'External Job link', 'Questions Found', 'Connect Request']
            writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
            if csv_file.tell() == 0: writer.writeheader()
            writer.writerow({'Job ID':job_id, 'Title':title, 'Company':company, 'Work Location':work_location, 'Work Style':work_style, 
                            'About Job':description, 'Experience required': experience_required, 'Skills required':skills, 
                                'HR Name':hr_name, 'HR Link':hr_link, 'Resume':resume, 'Re-posted':reposted, 
                                'Date Posted':date_listed, 'Date Applied':date_applied, 'Job Link':job_link, 
                                'External Job link':application_link, 'Questions Found':questions_list, 'Connect Request':connect_request})
        csv_file.close()
    except Exception as e:
        print_lg("Failed to update submitted jobs list!", e)
        pyautogui.alert("Failed to update the excel of applied jobs!\nProbably because of 1 of the following reasons:\n1. The file is currently open or in use by another program\n2. Permission denied to write to the file\n3. Failed to find the file", "Failed Logging")



def _element_is_visible(element) -> bool:
    try:
        return not hasattr(element, "is_displayed") or element.is_displayed()
    except Exception:
        return False


def _element_is_enabled(element) -> bool:
    try:
        return not hasattr(element, "is_enabled") or element.is_enabled()
    except Exception:
        return False


def _visible_easy_apply_modals(browser) -> list:
    try:
        modals = browser.find_elements(
            By.XPATH,
            '//div['
            'contains(concat(" ",normalize-space(@class)," ")," jobs-easy-apply-modal ") '
            'or @data-test-modal-id="easy-apply-modal"]',
        )
    except Exception:
        return []
    return [modal for modal in modals if _element_is_visible(modal)]


def _control_text(control) -> str:
    values = []
    try:
        values.append(str(control.text or ""))
    except Exception:
        pass
    for attribute in ("aria-label", "title", "data-control-name"):
        try:
            values.append(str(control.get_attribute(attribute) or ""))
        except Exception:
            continue
    return _normalized_form_text(" ".join(values))


def _localized_modal_action(control, action: str) -> bool:
    words = set(_control_text(control).split())
    if action == "close":
        return bool(words.intersection({
            "close", "dismiss", "cerrar", "fermer", "zamknij", "fechar",
            "schliessen", "chiudi", "sluiten",
        }))
    if action == "discard":
        return bool(words.intersection({
            "discard", "descartar", "abandon", "abandonner", "abandonar",
            "odrzuc", "verwerfen", "annulla",
        }))
    if action == "save":
        return bool(words.intersection({
            "save", "guardar", "enregistrer", "zapisz", "speichern",
            "salva", "bewaren",
        }))
    if action == "done":
        return bool(words.intersection({
            "done", "hecho", "termine", "gotowe", "fertig", "fatto",
        }))
    return False


def _scoped_action_buttons(scope, action: str) -> list:
    candidates = []
    xpaths = (
        './/button[contains(@class,"artdeco-modal__dismiss")]',
        ".//button",
    ) if action == "close" else (".//button",)
    for xpath in xpaths:
        try:
            for button in scope.find_elements(By.XPATH, xpath):
                if button not in candidates:
                    candidates.append(button)
        except Exception:
            continue
    return [
        button for button in candidates
        if _element_is_visible(button)
        and _element_is_enabled(button)
        and _localized_modal_action(button, action)
    ]


def _visible_modal_dialogs(browser) -> list:
    dialogs = []
    for xpath in (
        '//*[@role="dialog" or @role="alertdialog"]',
        '//*[contains(concat(" ",normalize-space(@class)," "),'
        '" artdeco-modal ")]',
        '//*[@data-test-modal-container]',
        '//*[contains(concat(" ",normalize-space(@class)," "),'
        '" artdeco-modal-overlay ")]',
    ):
        try:
            for dialog in browser.find_elements(By.XPATH, xpath):
                if dialog not in dialogs:
                    dialogs.append(dialog)
        except Exception:
            continue
    return [dialog for dialog in dialogs if _element_is_visible(dialog)]


def _visible_top_level_overlays(browser) -> list:
    overlays = _visible_modal_dialogs(browser)
    for modal in _visible_easy_apply_modals(browser):
        if modal not in overlays:
            overlays.append(modal)
    return overlays


def _abandonment_confirmation_text(dialog) -> bool:
    try:
        text = _normalized_form_text(dialog.text)
    except Exception:
        return False
    return any(phrase in text for phrase in (
        "save this application",
        "save your application",
        "save application for later",
        "return to this application later",
        "guardar esta solicitud",
        "guardar tu solicitud",
        "enregistrer cette candidature",
        "zapisz te aplikacje",
    ))


def _visible_abandonment_dialogs(browser) -> list:
    abandonment_dialogs = []
    for dialog in _visible_modal_dialogs(browser):
        discard_buttons = _scoped_action_buttons(dialog, "discard")
        save_buttons = _scoped_action_buttons(dialog, "save")
        if discard_buttons and (
            save_buttons or _abandonment_confirmation_text(dialog)
        ):
            abandonment_dialogs.append(dialog)
    return abandonment_dialogs


def _visible_discard_dialogs(browser) -> list:
    dialogs = _visible_abandonment_dialogs(browser)
    for dialog in _visible_modal_dialogs(browser):
        if dialog in dialogs:
            continue
        if (
            bool(_scoped_action_buttons(dialog, "discard"))
            or _localized_modal_action(dialog, "discard")
        ):
            dialogs.append(dialog)
    return dialogs


def _success_confirmation_text(modal) -> bool:
    try:
        text = _normalized_form_text(modal.text)
    except Exception:
        return False
    return any(phrase in text for phrase in (
        "your application was sent",
        "application was sent",
        "application submitted",
        "application has been submitted",
        "tu solicitud se ha enviado",
        "solicitud enviada",
        "votre candidature a ete envoyee",
        "candidature envoyee",
        "aplikacja zostala wyslana",
    ))


def _visible_success_modals(browser) -> list:
    return [
        modal for modal in _visible_top_level_overlays(browser)
        if _success_confirmation_text(modal)
    ]


def _success_dismiss_buttons(modal) -> list:
    try:
        buttons = [
            button for button in modal.find_elements(By.XPATH, ".//button")
            if _element_is_visible(button) and _element_is_enabled(button)
        ]
    except Exception:
        return []
    done = [
        button for button in buttons
        if _localized_modal_action(button, "done")
    ]
    not_now = [
        button for button in buttons
        if _control_text(button) in {
            "not now", "ahora no", "pas maintenant", "nie teraz"
        }
        and button not in done
    ]
    close = [
        button for button in buttons
        if _localized_modal_action(button, "close")
        and button not in done
        and button not in not_now
    ]
    return done + not_now + close


def _wait_for_success_modal_absent(browser, tracked_modals=None) -> bool:
    tracked_modals = list(
        tracked_modals
        if tracked_modals is not None
        else _visible_success_modals(browser)
    )
    for _ in range(10):
        visible_overlays = _visible_top_level_overlays(browser)
        tracked_remain = any(
            modal in visible_overlays and _element_is_visible(modal)
            for modal in tracked_modals
        )
        if not tracked_remain and not _visible_success_modals(browser):
            return True
        sleep(0.2)
    visible_overlays = _visible_top_level_overlays(browser)
    tracked_remain = any(
        modal in visible_overlays and _element_is_visible(modal)
        for modal in tracked_modals
    )
    return not tracked_remain and not _visible_success_modals(browser)


def _dismiss_confirmed_success_modal(browser) -> dict:
    """Dismiss only an already-confirmed post-submit modal."""
    success_modals = _visible_success_modals(browser)
    if not success_modals:
        return {
            "confirmed": False,
            "dismissed": False,
            "modal_remains_open": False,
            "action": "none",
        }

    # Prefer the visible modal's own Done, Not now, then close control. Update
    # profile is never eligible.
    for modal in _visible_success_modals(browser):
        for button in _success_dismiss_buttons(modal):
            try:
                button.click()
            except Exception:
                continue
            if _wait_for_success_modal_absent(browser, success_modals):
                return {
                    "confirmed": True,
                    "dismissed": True,
                    "modal_remains_open": False,
                    "action": "modal_dismiss",
                }

    # Retain the historical Escape only as a final bounded fallback after the
    # modal has already been classified as a confirmed success.
    try:
        actions.send_keys(Keys.ESCAPE).perform()
    except Exception:
        pass
    if _wait_for_success_modal_absent(browser, success_modals):
        return {
            "confirmed": True,
            "dismissed": True,
            "modal_remains_open": False,
            "action": "historical_escape",
        }

    visible_overlays = _visible_top_level_overlays(browser)
    modal_remains_open = any(
        modal in visible_overlays and _element_is_visible(modal)
        for modal in success_modals
    ) or bool(_visible_success_modals(browser))
    return {
        "confirmed": True,
        "dismissed": not modal_remains_open,
        "modal_remains_open": modal_remains_open,
        "action": "cleanup_failed" if modal_remains_open else "modal_dismiss",
    }


def _cleanup_confirmed_success_modal(browser, job_id: str = "") -> dict | None:
    dismissal = _dismiss_confirmed_success_modal(browser)
    if not dismissal["confirmed"]:
        return None
    result = {
        "success": dismissal["dismissed"],
        "reason_code": (
            "easy_apply_modal_closed"
            if dismissal["dismissed"]
            else "post_apply_success_modal_cleanup_failed"
        ),
        "modal_remains_open": dismissal["modal_remains_open"],
        "cleanup_needed": True,
        "close_used": dismissal["action"] in {
            "historical_escape", "modal_dismiss"
        },
        "discard_used": False,
        "attempt_count": 1,
        "success_confirmation": True,
    }
    print_lg(
        "Easy Apply cleanup "
        f"job_id={job_id or 'unknown'} "
        f"cleanup_result={'success' if result['success'] else 'failure'} "
        f"reason_code={result['reason_code']} "
        f"modal_remains_open={str(result['modal_remains_open']).lower()}"
    )
    return result


def _post_submit_validation_detected(
    form_modal,
    unresolved_required: set,
) -> bool:
    if unresolved_required:
        return True
    if form_modal is None or not _element_is_visible(form_modal):
        return False
    if _collect_invalid_required_fields(form_modal):
        return True
    try:
        errors = form_modal.find_elements(
            By.XPATH,
            './/*[@aria-invalid="true" or '
            'contains(@class,"artdeco-inline-feedback--error") or '
            'contains(@class,"fb-form-element__error-text")]',
        )
    except Exception:
        return False
    return any(_element_is_visible(error) for error in errors)


def _job_applied_state_detected(job, browser) -> bool:
    applied_labels = {
        "applied", "solicitud enviada", "candidature envoyee", "aplicado",
    }
    if job is not None:
        try:
            states = job.find_elements(
                By.XPATH,
                './/*[contains(@class,"job-card-container__footer-job-state")]',
            )
        except Exception:
            states = []
        for state in states:
            try:
                if (
                    _element_is_visible(state)
                    and _normalized_form_text(state.text) in applied_labels
                ):
                    return True
            except Exception:
                continue
        try:
            job_text = _normalized_form_text(job.text)
            if any(
                re.search(rf"(?<!\w){re.escape(label)}(?!\w)", job_text)
                for label in applied_labels
            ):
                return True
        except Exception:
            pass
    try:
        details_states = browser.find_elements(
            By.XPATH,
            '//*[contains(@class,"jobs-s-apply__application-link")]',
        )
    except Exception:
        details_states = []
    for state in details_states:
        try:
            if _element_is_visible(state):
                return True
        except Exception:
            continue
    return False


def _post_submit_snapshot(
    browser,
    form_modal,
    job,
    unresolved_required: set,
) -> dict:
    success_modals = _visible_success_modals(browser)
    overlays = _visible_top_level_overlays(browser)
    applied_state = _job_applied_state_detected(job, browser)
    if success_modals:
        status = "success"
    elif _post_submit_validation_detected(form_modal, unresolved_required):
        status = "validation_error"
    elif _find_job_search_safety_reminder(browser) is not None:
        status = "safety_warning"
    elif applied_state and not overlays:
        status = "success"
    else:
        status = "pending"
    return {
        "status": status,
        "success_modal_detected": bool(success_modals),
        "applied_state_detected": applied_state,
        "visible_overlay_count": len(overlays),
        "modal_remains_open": bool(overlays),
    }


def _wait_for_post_submit_state(
    browser,
    form_modal,
    job,
    unresolved_required: set,
    timeout_seconds: float = 12.0,
    poll_seconds: float = 0.25,
) -> dict:
    attempts = max(1, int(timeout_seconds / max(poll_seconds, 0.1)))
    snapshot = None
    for _ in range(attempts):
        snapshot = _post_submit_snapshot(
            browser, form_modal, job, unresolved_required
        )
        if snapshot["status"] != "pending":
            return snapshot
        sleep(poll_seconds)
    snapshot = snapshot or {
        "success_modal_detected": False,
        "applied_state_detected": False,
        "visible_overlay_count": 0,
        "modal_remains_open": False,
    }
    snapshot["status"] = "timeout"
    return snapshot


def _log_post_submit_state(
    job_id: str,
    state: dict,
    *,
    success_accounted: bool,
    cleanup_result: str,
    modal_remains_open: bool | None = None,
) -> None:
    remains_open = (
        state.get("modal_remains_open", False)
        if modal_remains_open is None
        else modal_remains_open
    )
    print_lg(
        "Post-submit wait "
        f"job_id={job_id or 'unknown'} submit_clicked=true "
        f"success_modal_detected={str(bool(state.get('success_modal_detected'))).lower()} "
        f"applied_state_detected={str(bool(state.get('applied_state_detected'))).lower()} "
        f"visible_overlay_count={int(state.get('visible_overlay_count') or 0)} "
        f"success_accounted={str(bool(success_accounted)).lower()} "
        f"cleanup_result={cleanup_result} "
        f"modal_remains_open={str(bool(remains_open)).lower()}"
    )


def _easy_apply_blocker_state(browser) -> tuple[list, list]:
    return _visible_easy_apply_modals(browser), _visible_discard_dialogs(browser)


def _cleanup_easy_apply_modal_once(browser) -> dict:
    modals, discard_dialogs = _easy_apply_blocker_state(browser)
    cleanup_needed = bool(modals or discard_dialogs)
    close_used = False
    discard_used = False

    # An already-open confirmation dialog is the active modal layer. Otherwise,
    # use only the Easy Apply modal's own dismiss control.
    if not discard_dialogs:
        for modal in modals:
            close_buttons = _scoped_action_buttons(modal, "close")
            if not close_buttons:
                continue
            try:
                close_buttons[0].click()
                close_used = True
            except Exception:
                continue

    modal_remains_open = True
    for _ in range(10):
        # The save-draft confirmation can appear after the close click. Re-scan
        # on every poll and click only its localized Discard action.
        for dialog in _visible_discard_dialogs(browser):
            discard_buttons = _scoped_action_buttons(dialog, "discard")
            if not discard_buttons:
                continue
            try:
                discard_buttons[0].click()
                discard_used = True
            except Exception:
                continue
        active_modals, active_discard_dialogs = _easy_apply_blocker_state(browser)
        modal_remains_open = bool(active_modals or active_discard_dialogs)
        if not modal_remains_open:
            break
        sleep(0.2)

    success = not modal_remains_open
    if not success:
        reason_code = "easy_apply_modal_cleanup_failed"
    elif discard_used:
        reason_code = "easy_apply_application_discarded"
    else:
        reason_code = "easy_apply_modal_closed"
    return {
        "success": success,
        "reason_code": reason_code,
        "modal_remains_open": modal_remains_open,
        "cleanup_needed": cleanup_needed,
        "close_used": close_used,
        "discard_used": discard_used,
        "success_confirmation": False,
    }


def _cleanup_easy_apply_modal(browser, job_id: str = "") -> dict:
    """Close only Easy Apply UI, retrying once and returning safe metadata."""
    if _visible_success_modals(browser):
        return {
            "success": False,
            "reason_code": "post_apply_success_modal_pending",
            "modal_remains_open": True,
            "cleanup_needed": True,
            "close_used": False,
            "discard_used": False,
            "attempt_count": 0,
            "success_confirmation": True,
        }
    aggregate_cleanup_needed = False
    aggregate_close_used = False
    aggregate_discard_used = False
    result = None
    for attempt_count in range(1, 3):
        result = _cleanup_easy_apply_modal_once(browser)
        aggregate_cleanup_needed = (
            aggregate_cleanup_needed or result["cleanup_needed"]
        )
        aggregate_close_used = aggregate_close_used or result["close_used"]
        aggregate_discard_used = aggregate_discard_used or result["discard_used"]
        if result["success"]:
            break

    result["attempt_count"] = attempt_count
    result["cleanup_needed"] = aggregate_cleanup_needed
    result["close_used"] = aggregate_close_used
    result["discard_used"] = aggregate_discard_used
    if result["success"]:
        result["reason_code"] = (
            "easy_apply_application_discarded"
            if aggregate_discard_used
            else "easy_apply_modal_closed"
        )
    if aggregate_cleanup_needed:
        _record_review_outcome("application_discarded", result["reason_code"])
        print_lg(
            "Easy Apply cleanup "
            f"job_id={job_id or 'unknown'} "
            f"cleanup_result={'success' if result['success'] else 'failure'} "
            f"reason_code={result['reason_code']} "
            f"modal_remains_open={str(result['modal_remains_open']).lower()}"
        )
    return result


def _classify_visible_overlays(browser) -> dict:
    overlays = _visible_top_level_overlays(browser)
    success = _visible_success_modals(browser)
    safety_dialog = _find_job_search_safety_reminder(browser)
    safety = [safety_dialog] if safety_dialog is not None else []
    abandonment = _visible_abandonment_dialogs(browser)
    unfinished = [
        modal for modal in _visible_easy_apply_modals(browser)
        if modal not in success
    ]
    classified = success + safety + abandonment + unfinished
    unknown = [overlay for overlay in overlays if overlay not in classified]
    return {
        "success": success,
        "safety": safety,
        "abandonment": abandonment,
        "unfinished": unfinished,
        "unknown": unknown,
        "overlay_count": len(overlays),
    }


def _guard_next_job_click(browser, job_id: str = "") -> dict:
    """Prevent job-card clicks while an Easy Apply layer is still active."""
    classification = _classify_visible_overlays(browser)
    if classification["success"]:
        return _cleanup_confirmed_success_modal(browser, job_id)
    if classification["safety"]:
        _detected, safely_closed = _close_job_search_safety_reminder(browser)
        if not safely_closed:
            return {
                "success": False,
                "reason_code": "easy_apply_modal_cleanup_failed",
                "modal_remains_open": True,
                "cleanup_needed": True,
                "close_used": False,
                "discard_used": False,
                "attempt_count": 1,
                "success_confirmation": False,
            }
        sleep(0.2)
        classification = _classify_visible_overlays(browser)
        if classification["success"]:
            return _cleanup_confirmed_success_modal(browser, job_id)
    if classification["abandonment"] or classification["unfinished"]:
        return _cleanup_easy_apply_modal(browser, job_id)
    if classification["unknown"]:
        result = {
            "success": False,
            "reason_code": "easy_apply_modal_cleanup_failed",
            "modal_remains_open": True,
            "cleanup_needed": True,
            "close_used": False,
            "discard_used": False,
            "attempt_count": 0,
            "success_confirmation": False,
        }
        print_lg(
            "Easy Apply cleanup "
            f"job_id={job_id or 'unknown'} cleanup_result=failure "
            "reason_code=easy_apply_modal_cleanup_failed "
            "modal_remains_open=true"
        )
        return result
    if not any(classification.values()):
        # Kept for defensive compatibility with non-dict test doubles.
        classification = {"overlay_count": 0}
    if not classification.get("overlay_count"):
        return {
            "success": True,
            "reason_code": "easy_apply_modal_closed",
            "modal_remains_open": False,
            "cleanup_needed": False,
            "close_used": False,
            "discard_used": False,
            "attempt_count": 0,
            "success_confirmation": False,
        }
    return {
        "success": False,
        "reason_code": "easy_apply_modal_cleanup_failed",
        "modal_remains_open": True,
        "cleanup_needed": True,
        "close_used": False,
        "discard_used": False,
        "attempt_count": 0,
        "success_confirmation": False,
    }


class JobSearchSafetyReminder(Exception):
    """Stop only the current application when LinkedIn shows a safety warning."""


def _find_job_search_safety_reminder(browser):
    for dialog in _visible_modal_dialogs(browser):
        try:
            title = dialog.find_elements(
                By.XPATH,
                './/*[normalize-space(.)="Job search safety reminder"]',
            )
            review_action = dialog.find_elements(
                By.XPATH,
                './/*[normalize-space(.)="Review job post"]',
            )
            continue_action = dialog.find_elements(
                By.XPATH,
                './/*[normalize-space(.)="Continue applying"]',
            )
            if title or (review_action and continue_action):
                return dialog
        except Exception:
            continue
    return None


def _close_job_search_safety_reminder(browser) -> tuple[bool, bool]:
    """Return (detected, safely_closed) without clicking warning actions."""
    dialog = _find_job_search_safety_reminder(browser)
    if dialog is None:
        return False, False
    try:
        close_buttons = dialog.find_elements(
            By.XPATH,
            './/button['
            'contains(@class,"artdeco-modal__dismiss") or '
            '@aria-label="Dismiss" or @aria-label="Close" or '
            '@aria-label="Cerrar"]',
        )
    except Exception:
        close_buttons = []
    for button in close_buttons:
        try:
            label = " ".join(str(button.text or "").casefold().split())
            if label in {"continue applying", "review job post"}:
                continue
            if button.is_displayed() and button.is_enabled():
                button.click()
                return True, True
        except Exception:
            continue
    return True, False


def _visible_enabled_submit_button(modal):
    try:
        if hasattr(modal, "is_displayed") and not modal.is_displayed():
            return None
        buttons = modal.find_elements(
            By.XPATH,
            './/button['
            'normalize-space(.)="Submit application" or '
            './/span[normalize-space(.)="Submit application"]]',
        )
    except Exception:
        return None
    for button in buttons:
        try:
            if (
                button.is_displayed()
                and button.is_enabled()
                and str(button.get_attribute("aria-disabled") or "").casefold()
                != "true"
                and str(button.get_attribute("disabled") or "").casefold()
                not in {"true", "disabled"}
            ):
                return button
        except Exception:
            continue
    return None


def _final_review_reached_from_submit_button(
    modal,
    unresolved_required: set,
) -> bool:
    if unresolved_required or _collect_invalid_required_fields(modal):
        return False
    return _visible_enabled_submit_button(modal) is not None






# Function to apply to jobs
def apply_to_jobs(search_terms: list[str]) -> None:
    applied_jobs = get_applied_job_ids()
    rejected_jobs = set()
    blacklisted_companies = set()
    global current_city, failed_count, skip_count, easy_applied_count, external_jobs_count, tabs_count, pause_before_submit, pause_at_failed_question, useNewResume, ai_review_context
    current_city = current_city.strip()

    if randomize_search_order:  shuffle(search_terms)
    for searchTerm in search_terms:
        stop_current_search_term_scan = False
        driver.get(f"https://www.linkedin.com/jobs/search/?keywords={searchTerm}")
        print_lg("\n________________________________________________________________________________________________________________________\n")
        print_lg(f'\n>>>> Now searching for "{searchTerm}" <<<<\n\n')

        apply_filters()

        current_count = 0
        try:
            while current_count < switch_number:
                # Wait until job listings are loaded
                #CR:Jinhao
                wait.until(EC.presence_of_all_elements_located((By.XPATH, "//li[contains(@class, 'occludable-update')]")))

                pagination_element, current_page = get_page_info()

                # Find all job listings in current page
                buffer(3)
                job_listings = driver.find_elements(By.XPATH, "//li[contains(@class, 'occludable-update')]")  

            
                for job in job_listings:
                    if keep_screen_awake: pyautogui.press('shiftright')
                    if current_count >= switch_number: break
                    print_lg("\n-@-\n")

                    prior_job_id = str(
                        globals().get("ai_review_context", {}).get("job_id", "")
                    )
                    cleanup_guard = _guard_next_job_click(driver, prior_job_id)
                    if not cleanup_guard["success"]:
                        stop_current_search_term_scan = True
                        break

                    job_id,title,company,work_location,work_style,skip = get_job_main_details(job, blacklisted_companies, rejected_jobs)
                    ai_review_context = {
                        "job_id": job_id,
                        "company": company,
                        "job_title": title,
                    }
                    
                    if skip: continue
                    # Redundant fail safe check for applied jobs!
                    try:
                        if job_id in applied_jobs or find_by_class(driver, "jobs-s-apply__application-link", 2):
                            print_lg(f'Already applied to "{title} | {company}" job. Job ID: {job_id}!')
                            continue
                    except Exception as e:
                        print_lg(f'Trying to Apply to "{title} | {company}" job. Job ID: {job_id}')

                    job_link = "https://www.linkedin.com/jobs/view/"+job_id
                    application_link = "Easy Applied"
                    date_applied = "Pending"
                    hr_link = "Unknown"
                    hr_name = "Unknown"
                    connect_request = "In Development" # Still in development
                    date_listed = "Unknown"
                    skills = "Needs an AI" # Still in development
                    resume = "Pending"
                    reposted = False
                    questions_list = None
                    screenshot_name = "Not Available"
                    stop_after_submitted_cleanup = False
                    post_submit_success_confirmed = False
                    post_submit_success_modal_detected = False
                    post_submit_state = None

                    try:
                        rejected_jobs, blacklisted_companies, jobs_top_card = check_blacklist(rejected_jobs,job_id,company,blacklisted_companies)
                    except ValueError as e:
                        print_lg(e, 'Skipping this job!\n')
                        failed_job(job_id, job_link, resume, date_listed, "Found Blacklisted words in About Company", e, "Skipped", screenshot_name)
                        skip_count += 1
                        continue
                    except Exception as e:
                        print_lg("Failed to scroll to About Company!")
                        # print_lg(e)



                    # Hiring Manager info
                    try:
                        hr_info_card = WebDriverWait(driver,2).until(EC.presence_of_element_located((By.CLASS_NAME, "hirer-card__hirer-information")))
                        hr_link = hr_info_card.find_element(By.TAG_NAME, "a").get_attribute("href")
                        hr_name = hr_info_card.find_element(By.TAG_NAME, "span").text
                        # if connect_hr:
                        #     driver.switch_to.new_window('tab')
                        #     driver.get(hr_link)
                        #     wait_span_click("More")
                        #     wait_span_click("Connect")
                        #     wait_span_click("Add a note")
                        #     message_box = driver.find_element(By.XPATH, "//textarea")
                        #     message_box.send_keys(connect_request_message)
                        #     if close_tabs: driver.close()
                        #     driver.switch_to.window(linkedIn_tab) 
                        # def message_hr(hr_info_card):
                        #     if not hr_info_card: return False
                        #     hr_info_card.find_element(By.XPATH, ".//span[normalize-space()='Message']").click()
                        #     message_box = driver.find_element(By.XPATH, "//div[@aria-label='Write a message…']")
                        #     message_box.send_keys()
                        #     try_xp(driver, "//button[normalize-space()='Send']")        
                    except Exception as e:
                        print_lg(f'HR info was not given for "{title}" with Job ID: {job_id}!')
                        # print_lg(e)


                    # Calculation of date posted
                    try:
                        # try: time_posted_text = find_by_class(driver, "jobs-unified-top-card__posted-date", 2).text
                        # except: 
                        time_posted_text = jobs_top_card.find_element(By.XPATH, './/span[contains(normalize-space(), " ago")]').text
                        print("Time Posted: " + time_posted_text)
                        if time_posted_text.__contains__("Reposted"):
                            reposted = True
                            time_posted_text = time_posted_text.replace("Reposted", "")
                        date_listed = calculate_date_posted(time_posted_text)
                    except Exception as e:
                        print_lg("Failed to calculate the date posted!",e)


                    description, experience_required, skip, reason, message = get_job_description()
                    if skip:
                        print_lg(message)
                        failed_job(job_id, job_link, resume, date_listed, reason, message, "Skipped", screenshot_name)
                        rejected_jobs.add(job_id)
                        skip_count += 1
                        continue

                    
                    if use_AI and description != "Unknown":
                        skills = ai_extract_skills(aiClient, description)

                    uploaded = False
                    # Case 1: Easy Apply Button
                    if try_xp(driver, ".//button[contains(@class,'jobs-apply-button') and contains(@class, 'artdeco-button--3') and contains(@aria-label, 'Easy')]"):
                        unresolved_required = set()
                        try: 
                            try:
                                errored = ""
                                safety_warning_active = False
                                safety_detected, safety_closed = (
                                    _close_job_search_safety_reminder(driver)
                                )
                                if safety_detected:
                                    safety_warning_active = True
                                    _record_review_outcome(
                                        "safety_warning_skipped",
                                        "job_search_safety_reminder",
                                    )
                                    raise JobSearchSafetyReminder(
                                        "Safety reminder closed"
                                        if safety_closed
                                        else "Safety reminder could not be closed safely"
                                    )
                                modal = find_by_class(driver, "jobs-easy-apply-modal")
                                wait_span_click(modal, "Next", 1)
                                # if description != "Unknown":
                                #     resume = create_custom_resume(description)
                                resume = "Previous resume"
                                next_button = True
                                questions_list = set()
                                reached_review = False
                                final_review_reason = ""
                                next_counter = 0
                                repaired_page_signatures = set()
                                while next_button:
                                    safety_detected, safety_closed = (
                                        _close_job_search_safety_reminder(driver)
                                    )
                                    if safety_detected:
                                        safety_warning_active = True
                                        _record_review_outcome(
                                            "safety_warning_skipped",
                                            "job_search_safety_reminder",
                                        )
                                        raise JobSearchSafetyReminder(
                                            "Safety reminder closed"
                                            if safety_closed
                                            else "Safety reminder could not be closed safely"
                                        )
                                    next_counter += 1
                                    questions_list = answer_questions(modal, questions_list, work_location, title, unresolved_required, job_description=description)

                                    if next_counter >= 15:
                                        if questions_list: print_lg("Stuck for one or some of the following questions...", questions_list)
                                        screenshot_name = screenshot(driver, job_id, "Failed at questions")
                                        errored = "stuck"
                                        _record_review_outcome(
                                            "application_discarded",
                                            "failed_question_unresolved",
                                        )
                                        raise Exception("Seems like stuck in a continuous loop of next, probably because of new questions.")

                                    if useNewResume and not uploaded: uploaded, resume = upload_resume(modal, default_resume_path)
                                    if _final_review_reached_from_submit_button(
                                        modal, unresolved_required
                                    ):
                                        reached_review = True
                                        final_review_reason = (
                                            "final_review_detected_from_submit_button"
                                        )
                                        break
                                    try:
                                        next_button = modal.find_element(By.XPATH, './/span[normalize-space(.)="Review"]')
                                        reached_review = True
                                    except NoSuchElementException:  next_button = modal.find_element(By.XPATH, './/button[contains(span, "Next")]')
                                    before_signature = _form_page_signature(modal)
                                    try: 
                                        next_button.click()

                                    except ElementClickInterceptedException: break    # Happens when it tries to click Next button in About Company photos section
                                    buffer(click_gap)
                                    repair_result = _repair_after_failed_advance(
                                        modal,
                                        before_signature,
                                        work_location,
                                        title,
                                        description,
                                        unresolved_required,
                                        repaired_page_signatures,
                                    )
                                    if repair_result is False:
                                        raise Exception("Required application fields remain unresolved")
                                    if repair_result is True:
                                        next_button.click()
                                        buffer(click_gap)
                                        if _form_page_signature(modal) == before_signature:
                                            raise Exception("Required application fields remain unresolved after repair")
                                        next_counter = 1

                            except NoSuchElementException:
                                safety_detected, safety_closed = (
                                    _close_job_search_safety_reminder(driver)
                                )
                                if safety_detected:
                                    safety_warning_active = True
                                    _record_review_outcome(
                                        "safety_warning_skipped",
                                        "job_search_safety_reminder",
                                    )
                                    raise JobSearchSafetyReminder(
                                        "Safety reminder closed"
                                        if safety_closed
                                        else "Safety reminder could not be closed safely"
                                    )
                                errored = "nose"
                            finally:
                                if safety_warning_active:
                                    raise
                                if questions_list and errored != "stuck": 
                                    print_lg("Answered the following questions...", questions_list)
                                    print("\n\n" + "\n".join(str(question) for question in questions_list) + "\n\n")
                                if (
                                    not unresolved_required
                                    and wait_span_click(
                                        driver, "Review", 1, scrollTop=True
                                    )
                                ):
                                    reached_review = True
                                if (
                                    not reached_review
                                    and _final_review_reached_from_submit_button(
                                        modal, unresolved_required
                                    )
                                ):
                                    reached_review = True
                                    final_review_reason = (
                                        "final_review_detected_from_submit_button"
                                    )
                                if unresolved_required or not reached_review or current_count >= switch_number:
                                    reason = "unresolved_required_fields" if unresolved_required else "review_not_reached_or_limit"
                                    print_lg(f"Submit guard blocked application reason_code={reason}")
                                    raise Exception(f"Submit guard blocked application: {reason}")
                                _record_review_outcome(
                                    "reached_review", final_review_reason
                                )
                                cur_pause_before_submit = pause_before_submit
                                if errored != "stuck" and cur_pause_before_submit:
                                    decision = pyautogui.confirm('1. Please verify your information.\n2. If you edited something, please return to this final screen.\n3. DO NOT CLICK "Submit Application".\n\n\n\n\nYou can turn off "Pause before submit" setting in config.py\nTo TEMPORARILY disable pausing, click "Disable Pause"', "Confirm your information",["Disable Pause", "Discard Application", "Submit Application"])
                                    if decision == "Discard Application": raise Exception("Job application discarded by user!")
                                    pause_before_submit = False if "Disable Pause" == decision else True
                                    # try_xp(modal, ".//span[normalize-space(.)='Review']")
                                follow_company(modal)
                                if wait_span_click(driver, "Submit application", 2, scrollTop=True): 
                                    post_submit_state = _wait_for_post_submit_state(
                                        driver,
                                        modal,
                                        job,
                                        unresolved_required,
                                    )
                                    if post_submit_state["status"] == "success":
                                        date_applied = datetime.now()
                                        post_submit_success_confirmed = True
                                        post_submit_success_modal_detected = bool(
                                            post_submit_state[
                                                "success_modal_detected"
                                            ]
                                        )
                                        ai_review_context["application_submitted"] = True
                                        _record_review_outcome("submitted")
                                        _log_post_submit_state(
                                            job_id,
                                            post_submit_state,
                                            success_accounted=True,
                                            cleanup_result="pending",
                                        )
                                    elif post_submit_state["status"] == "safety_warning":
                                        raise JobSearchSafetyReminder(
                                            "Safety reminder detected after submit"
                                        )
                                    elif post_submit_state["status"] == "validation_error":
                                        raise Exception(
                                            "Post-submit validation blocked submission"
                                        )
                                    else:
                                        _log_post_submit_state(
                                            job_id,
                                            post_submit_state,
                                            success_accounted=False,
                                            cleanup_result="timeout",
                                        )
                                        raise Exception(
                                            "Post-submit confirmation timed out"
                                        )
                                else:
                                    print_lg("Since, Submit Application failed, discarding the job application...")
                                    # if screenshot_name == "Not Available":  screenshot_name = screenshot(driver, job_id, "Failed to click Submit application")
                                    # else:   screenshot_name = [screenshot_name, screenshot(driver, job_id, "Failed to click Submit application")]
                                    raise Exception("Failed to click Submit application")


                        except JobSearchSafetyReminder as e:
                            cleanup_result = _cleanup_easy_apply_modal(driver, job_id)
                            failed_job(
                                job_id,
                                job_link,
                                resume,
                                date_listed,
                                "Job search safety reminder",
                                e,
                                "Skipped",
                                screenshot_name,
                            )
                            rejected_jobs.add(job_id)
                            skip_count += 1
                            if not cleanup_result["success"]:
                                stop_current_search_term_scan = True
                                break
                            continue
                        except Exception as e:
                            cleanup_result = _cleanup_easy_apply_modal(driver, job_id)
                            if cleanup_result.get("success_confirmation"):
                                if not ai_review_context.get("application_submitted"):
                                    date_applied = datetime.now()
                                    ai_review_context["application_submitted"] = True
                                    _record_review_outcome("submitted")
                                post_submit_success_confirmed = True
                                post_submit_success_modal_detected = True
                                post_submit_state = {
                                    "status": "success",
                                    "success_modal_detected": True,
                                    "applied_state_detected": (
                                        _job_applied_state_detected(job, driver)
                                    ),
                                    "visible_overlay_count": len(
                                        _visible_top_level_overlays(driver)
                                    ),
                                    "modal_remains_open": True,
                                }
                            else:
                                print_lg("Failed to Easy apply!")
                                # print_lg(e)
                                critical_error_log("Somewhere in Easy Apply process",e)
                                failed_job(job_id, job_link, resume, date_listed, "Problem in Easy Applying", e, application_link, screenshot_name)
                                failed_count += 1
                                if not cleanup_result["success"]:
                                    stop_current_search_term_scan = True
                                    break
                                continue
                    else:
                        # Case 2: Apply externally
                        skip, application_link, tabs_count = external_apply(pagination_element, job_id, job_link, resume, date_listed, application_link, screenshot_name)
                        if dailyEasyApplyLimitReached:
                            print_lg("\n###############  Daily application limit for Easy Apply is reached!  ###############\n")
                            return
                        if skip: continue

                    submitted_jobs(job_id, title, company, work_location, work_style, description, experience_required, skills, hr_name, hr_link, resume, reposted, date_listed, date_applied, job_link, application_link, questions_list, connect_request)
                    if uploaded:   useNewResume = False

                    print_lg(f'Successfully saved "{title} | {company}" job. Job ID: {job_id} info')
                    current_count += 1
                    if application_link == "Easy Applied": easy_applied_count += 1
                    else:   external_jobs_count += 1
                    applied_jobs.add(job_id)
                    if post_submit_success_confirmed:
                        if post_submit_success_modal_detected:
                            success_cleanup = _cleanup_confirmed_success_modal(
                                driver, job_id
                            )
                            if success_cleanup is None:
                                success_cleanup = {
                                    "success": True,
                                    "reason_code": "easy_apply_modal_closed",
                                    "modal_remains_open": False,
                                }
                        else:
                            success_cleanup = {
                                "success": True,
                                "reason_code": "easy_apply_modal_closed",
                                "modal_remains_open": False,
                            }
                        stop_after_submitted_cleanup = not success_cleanup["success"]
                        if stop_after_submitted_cleanup:
                            _record_review_outcome(
                                "submitted",
                                "post_apply_success_modal_cleanup_failed",
                            )
                        _log_post_submit_state(
                            job_id,
                            post_submit_state or {},
                            success_accounted=True,
                            cleanup_result=success_cleanup["reason_code"],
                            modal_remains_open=success_cleanup[
                                "modal_remains_open"
                            ],
                        )
                    if stop_after_submitted_cleanup:
                        stop_current_search_term_scan = True
                        break
                
                # Pause update---
                # --- Anti-rate-limit pause between applications ---
                    from random import uniform
                    pause_duration = round(uniform(15, 25), 2)  # 5–12 s random delay
                    print_lg(f"🕒 Pausing {pause_duration}s before next application to mimic human rhythm...")
                    sleep(pause_duration)
                # from random import uniform
                # sleep(uniform(1, 5))   # wait 5–10 seconds between applications
                # print_lg(f"🕒 Short pause between applications to mimic human behavior...")


                if stop_current_search_term_scan:
                    break



                # Switching to next page
                # if pagination_element == None:
                #     print_lg("Couldn't find pagination element, probably at the end page of results!")
                #     break
                # try:
                #     pagination_element.find_element(By.XPATH, f"//button[@aria-label='Page {current_page+1}']").click()
                #     print_lg(f"\n>-> Now on Page {current_page+1} \n")
                # except NoSuchElementException:
                #     print_lg(f"\n>-> Didn't find Page {current_page+1}. Probably at the end page of results!\n")
                #     break# Switching to next page
                    
                   # Switching to the next page
                # Switching to next page
                try:
                    next_button = driver.find_element(By.XPATH, "//button[contains(@class, 'jobs-search-pagination__button--next') and @aria-label='View next page']")
                    
                    if "artdeco-button--disabled" in next_button.get_attribute("class"):
                        print_lg("\n>-> 'Next' button is disabled. Reached the last page!\n")
                        break 
                    
                    driver.execute_script("arguments[0].scrollIntoView();", next_button)  # Ensure it's in view
                    sleep(1)  # Small delay for stability
                    next_button.click()
                    
                    print_lg("\n>-> Clicked 'Next' button. Moving to the next page...\n")
                    sleep(3)  # Allow time for page to load
                except NoSuchElementException:
                    print_lg("\n⚠️ 'Next' button not found. Stopping pagination.\n")
                    break
            
        except Exception as e:
            print_lg("Failed to find Job listings!")
            critical_error_log("In Applier", e)
            print_lg("Job listing scan failed; full page diagnostics suppressed.")
            # print_lg(e)

        
def run(total_runs: int) -> int:
    if dailyEasyApplyLimitReached:
        return total_runs
    print_lg("\n########################################################################################################################\n")
    print_lg(f"Date and Time: {datetime.now()}")
    print_lg(f"Cycle number: {total_runs}")
    print_lg(f"Currently looking for jobs posted within '{date_posted}' and sorting them by '{sort_by}'")
    apply_to_jobs(search_terms)
    print_lg("########################################################################################################################\n")
    if not dailyEasyApplyLimitReached:
        print_lg("Sleeping for 10 min...")
        sleep(10)
        print_lg("Few more min... Gonna start with in next 5 min...")
        sleep(10)
    buffer(3)
    return total_runs + 1



chatGPT_tab = False
linkedIn_tab = False

def main() -> None:
    try:
        global linkedIn_tab, tabs_count, useNewResume, aiClient, ai_answer_review_queue
        ai_answer_review_queue = AIAnswerReviewQueue()
        alert_title = "Error Occurred. Closing Browser!"
        total_runs = 1        
        validate_config()
        
        if not os.path.exists(default_resume_path):
            pyautogui.alert(text='Your default resume "{}" is missing! Please update it\'s folder path "default_resume_path" in config.py\n\nOR\n\nAdd a resume with exact name and path (check for spelling mistakes including cases).\n\n\nFor now the bot will continue using your previous upload from LinkedIn!'.format(default_resume_path), title="Missing Resume", button="OK")
            useNewResume = False
        
        # Login to LinkedIn
        tabs_count = len(driver.window_handles)
        driver.get("https://www.linkedin.com/login")
        if not is_logged_in_LN(): login_LN()
        
        linkedIn_tab = driver.current_window_handle

        # # Login to ChatGPT in a new tab for resume customization
        # if use_resume_generator:
        #     try:
        #         driver.switch_to.new_window('tab')
        #         driver.get("https://chat.openai.com/")
        #         if not is_logged_in_GPT(): login_GPT()
        #         open_resume_chat()
        #         global chatGPT_tab
        #         chatGPT_tab = driver.current_window_handle
        #     except Exception as e:
        #         print_lg("Opening OpenAI chatGPT tab failed!")
        if use_AI:
            aiClient = ai_create_openai_client()

        # Start applying to jobs
        driver.switch_to.window(linkedIn_tab)
        total_runs = run(total_runs)
        while(run_non_stop):
            if cycle_date_posted:
                date_options = ["Any time", "Past month", "Past week", "Past 24 hours"]
                global date_posted
                date_posted = date_options[date_options.index(date_posted)+1 if date_options.index(date_posted)+1 > len(date_options) else -1] if stop_date_cycle_at_24hr else date_options[0 if date_options.index(date_posted)+1 >= len(date_options) else date_options.index(date_posted)+1]
            if alternate_sortby:
                global sort_by
                sort_by = "Most recent" if sort_by == "Most relevant" else "Most relevant"
                total_runs = run(total_runs)
                sort_by = "Most recent" if sort_by == "Most relevant" else "Most relevant"
            total_runs = run(total_runs)
            if dailyEasyApplyLimitReached:
                break
        

    except NoSuchWindowException:
        if ai_answer_review_queue is not None:
            ai_answer_review_queue.record_run_interrupted()
    except KeyboardInterrupt:
        if ai_answer_review_queue is not None:
            ai_answer_review_queue.record_run_interrupted()
        raise
    except Exception as e:
        if ai_answer_review_queue is not None:
            ai_answer_review_queue.record_run_interrupted()
        critical_error_log("In Applier Main", e)
        pyautogui.alert(e,alert_title)
    finally:
        if ai_answer_review_queue is not None:
            ai_answer_review_queue.print_summary()
            ai_answer_review_queue.close()
        print_lg("\n\nTotal runs:                     {}".format(total_runs))
        print_lg("Jobs Easy Applied:              {}".format(easy_applied_count))
        print_lg("External job links collected:   {}".format(external_jobs_count))
        print_lg("                              ----------")
        print_lg("Total applied or collected:     {}".format(easy_applied_count + external_jobs_count))
        print_lg("\nFailed jobs:                    {}".format(failed_count))
        print_lg("Irrelevant jobs skipped:        {}\n".format(skip_count))
        if randomly_answered_questions: print_lg("\n\nQuestions randomly answered:\n  {}  \n\n".format(";\n".join(str(question) for question in randomly_answered_questions)))
        quote = choice([
            "You're one step closer than before.", 
            "All the best with your future interviews.", 
            "Keep up with the progress. You got this.", 
            "If you're tired, learn to take rest but never give up.",
            "Success is not final, failure is not fatal: It is the courage to continue that counts. - Winston Churchill",
            "Believe in yourself and all that you are. Know that there is something inside you that is greater than any obstacle. - Christian D. Larson",
            "Every job is a self-portrait of the person who does it. Autograph your work with excellence.",
            "The only way to do great work is to love what you do. If you haven't found it yet, keep looking. Don't settle. - Steve Jobs",
            "Opportunities don't happen, you create them. - Chris Grosser",
            "The road to success and the road to failure are almost exactly the same. The difference is perseverance.",
            "Obstacles are those frightful things you see when you take your eyes off your goal. - Henry Ford",
            "The only limit to our realization of tomorrow will be our doubts of today. - Franklin D. Roosevelt"
            ])
        msg = f"\n{quote}\n\n\nBest regards,\nSai Vignesh Golla\nhttps://www.linkedin.com/in/saivigneshgolla/\n\n"
        pyautogui.alert(msg, "Exiting..")
        print_lg(msg,"Closing the browser...")
        if tabs_count >= 10:
            msg = "NOTE: IF YOU HAVE MORE THAN 10 TABS OPENED, PLEASE CLOSE OR BOOKMARK THEM!\n\nOr it's highly likely that application will just open browser and not do anything next time!" 
            pyautogui.alert(msg,"Info")
            print_lg("\n"+msg)
        ai_close_openai_client(aiClient)
        try: driver.quit()
        except Exception as e: critical_error_log("When quitting...", e)


if __name__ == "__main__":
    main()
