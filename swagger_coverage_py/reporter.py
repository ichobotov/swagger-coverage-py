import json
import os
import platform
import re
import shutil
import subprocess
from pathlib import Path
from typing import List

import requests

from swagger_coverage_py.configs import API_DOCS_FORMAT, DEBUG_MODE
from swagger_coverage_py.docs_writers.api_doc_writer import write_api_doc_to_file



class CoverageReporter:
    def __init__(self, api_name: str, host: str, verify: bool = True):
        self.host = host
        self.verify = verify
        self.swagger_doc_file = f"swagger-doc-{api_name}.{API_DOCS_FORMAT}"
        self.output_dir = self.__get_output_dir()
        self.swagger_coverage_config = f"swagger-coverage-config-{api_name}.json"
        self.ignored_paths = self.__get_ignored_paths_from_config()

    def __get_output_dir(self):
        output_dir = "swagger-coverage-output"
        subdir = re.match(r"(^\w*)://(.*)", self.host).group(2).replace('.','_').replace(':','_')
        if platform.system() == "Windows":
            return f"{output_dir}\\{subdir}"
        else:
            return f"{output_dir}/{subdir}"

    def __get_ignored_paths_from_config(self) -> List[str]:
        """Reads the swagger-coverage-config-<api_name>.json file and returns
        a list of endpoints/paths to exclude from the report

        """
        paths_to_ignore = []
        if not self.swagger_coverage_config:
            return paths_to_ignore

        print("Ignored paths-----", paths_to_ignore)
        if platform.system() == "Windows":
            conf_file = (Path(__file__).resolve().parents[4]).joinpath(f'{self.swagger_coverage_config}')
        else:
            conf_file = self.swagger_coverage_config
        with open(conf_file, "r") as file:
            data = json.load(file)
            paths = data.get("rules").get("paths", {})
            if paths.get("enable", False):
                paths_to_ignore = paths.get("ignore")

        return paths_to_ignore

    def setup(
        self, path_to_swagger_json: str, auth: object = None, cookies: dict = None
    ):
        """Setup all required attributes to generate report

        :param path_to_swagger_json: The relative URL path to the swagger.json (example: "/docs/api")
        :param auth: Authentication object acceptable by "requests" library
        :param cookies: Cookies dictionary. (Usage example: set this to bypass Okta auth locally)

        """
        link_to_swagger_json = f"{self.host}{path_to_swagger_json}"

        response = requests.get(
            link_to_swagger_json, auth=auth, cookies=cookies, verify=self.verify
        )
        assert response.ok, (
            f"Swagger doc is not pulled. See details: "
            f"{response.status_code} {response.request.url}"
            f"{response.content}\n{response.content}"
        )
        if self.swagger_coverage_config:
            write_api_doc_to_file(
                self.swagger_doc_file,
                api_doc_data=response,
                paths_to_delete=self.ignored_paths,
            )

    def generate_report(self):
        inner_location = "swagger-coverage-commandline/bin/swagger-coverage-commandline"
        
        cmd_path = os.path.join(os.path.dirname(__file__), inner_location)
        assert Path(
            cmd_path
        ).exists(), (
            f"No commandline tools is found in following locations:\n{cmd_path}\n"
        )
        command = [cmd_path, "-s", self.swagger_doc_file, "-i", self.output_dir]
        if self.swagger_coverage_config:
            command.extend(["-c", self.swagger_coverage_config])

        # Adjust the file paths for Windows
        if platform.system() == "Windows":
            command = [arg.replace("/", "\\") for arg in command]
        if platform.system() == "Windows":
            os.chdir(Path(__file__).resolve().parents[4])
            shutil.copy(os.path.join(os.path.dirname(__file__),'swagger-coverage-commandline','bin','swagger-coverage-commandline'), os.getcwd())
            shutil.copy(os.path.join(os.path.dirname(__file__),'swagger-coverage-commandline','bin','swagger-coverage-commandline.bat'), os.getcwd())
            shutil.copytree(
                os.path.join( os.getcwd(), 'swagger-coverage-output'),
                    os.path.join(os.path.dirname(__file__),'swagger-coverage-commandline','bin','swagger-coverage-output'))
            shutil.copy(
                os.path.join(
                    os.getcwd(),'swagger-coverage-config-dm-api-account.json'),
                    os.path.join(os.path.dirname(__file__),'swagger-coverage-commandline','bin'))
            shutil.copy(
                os.path.join(
                    os.getcwd(),'swagger-doc-dm-api-account.json'),
                    os.path.join(os.path.dirname(__file__),'swagger-coverage-commandline','bin'))
            subprocess.run(
                ['sh', 'swagger-coverage-commandline',
                 '-s', self.swagger_doc_file,
                 '-i', self.output_dir,
                 '-c', self.swagger_coverage_config],
                cwd=os.path.join(os.path.dirname(__file__), 'swagger-coverage-commandline','bin')
            )
            if Path(os.path.join(os.getcwd(),'swagger-coverage-report-dm-api-account.html')).exists():
                os.remove('swagger-coverage-report-dm-api-account.html')
            shutil.move(
                os.path.join(
                    os.path.dirname(__file__), 'swagger-coverage-commandline', 'bin', 'swagger-coverage-report-dm-api-account.html'
                    ), os.getcwd()
                )
            os.remove('swagger-coverage-commandline')
            os.remove('swagger-coverage-commandline.bat')
            os.remove(os.path.join(os.path.dirname(__file__),'swagger-coverage-commandline','bin', 'swagger-coverage-config-dm-api-account.json'))
            os.remove(os.path.join(os.path.dirname(__file__), 'swagger-coverage-commandline', 'bin','swagger-doc-dm-api-account.json'))
            shutil.rmtree(os.path.join(os.path.dirname(__file__), 'swagger-coverage-commandline', 'bin','swagger-coverage-output'))
        else:
            # Suppress all output if not in debug mode
            if not DEBUG_MODE:
                with open(os.devnull, 'w') as devnull:
                    subprocess.run(command, stdout=devnull, stderr=devnull)
            else:
                subprocess.run(command)



    def cleanup_input_files(self):
        shutil.rmtree(self.output_dir, ignore_errors=True)
        # Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        (Path(__file__).resolve().parents[5]).joinpath(self.output_dir).mkdir(parents=True, exist_ok=True)
