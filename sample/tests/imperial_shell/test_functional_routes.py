from fastapi import HTTPException, status
from sample.src.imperative_shell.functional_routes import functional_post_folder
from bson import ObjectId
import pytest

from sample.src.models import Organization, NoteFolder
from sample.src.schemas import FolderCreate

ORGANIZATION_ID = "000000000000000000000001"
PARENT_FOLDER_ID = "000000000000000000000002"


@pytest.fixture
def organization() -> Organization:
    return Organization(id=ObjectId(ORGANIZATION_ID), name="Test Org")


@pytest.fixture
def folder_create(organization: Organization) -> FolderCreate:
    return FolderCreate(
        name="Test Folder", organization_id=str(organization.id), parent_id=None
    )


@pytest.fixture
def parent_folder(organization: Organization) -> NoteFolder:
    return NoteFolder(
        id=ObjectId(PARENT_FOLDER_ID),
        name="Parent Folder",
        organization_id=str(organization.id),
        parent_id=None,
    )


@pytest.mark.parametrize("with_parent", [True, False])
def test_functional_post_folder_happy_path(
    with_parent: bool,
    folder_create: FolderCreate,
    organization: Organization,
    parent_folder: NoteFolder,
) -> None:
    result = functional_post_folder(
        organization,
        folder_create.model_copy(
            update={"parent_id": str(parent_folder.id) if with_parent else None}
        ),
        parent_folder if with_parent else None,
    )
    assert isinstance(result, NoteFolder)
    assert result.name == folder_create.name
    assert result.organization_id == str(organization.id)
    assert result.parent_id == (str(parent_folder.id) if with_parent else None)


@pytest.mark.parametrize(
    "auth_result, folder, parent_folder_org_id, expected_status_code, expected_text_pattern",
    [
        pytest.param(
            HTTPException(status_code=403, detail="foobar"),
            FolderCreate(
                name="Test Folder", organization_id=ORGANIZATION_ID, parent_id=None
            ),
            None,
            status.HTTP_403_FORBIDDEN,
            "foobar",
            id="auth_result_is_HTTPException",
        ),
        pytest.param(
            None,
            FolderCreate(
                name="Test Folder", organization_id=ORGANIZATION_ID, parent_id=None
            ),
            None,
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Organization does not exist",
            id="auth_result_is_None",
        ),
        pytest.param(
            ORGANIZATION_ID,
            FolderCreate(
                name="Test Folder",
                organization_id=ORGANIZATION_ID,
                parent_id=PARENT_FOLDER_ID,
            ),
            None,
            422,
            "Parent folder does not exist",
            id="parent_is_None",
        ),
        pytest.param(
            ORGANIZATION_ID,
            FolderCreate(
                name="Test Folder",
                organization_id=ORGANIZATION_ID,
                parent_id=PARENT_FOLDER_ID,
            ),
            "999999999999999999999999",
            422,
            "Parent and child organization mismatch",
            id="parent_and_child_organization_mismatch",
        ),
    ],
)
def test_functional_post_folder_error_cases(
    auth_result: str | HTTPException | None,
    folder: FolderCreate,
    parent_folder_org_id: str | None,
    expected_status_code: int,
    expected_text_pattern: str,
) -> None:
    with pytest.raises(HTTPException) as exc_info:
        functional_post_folder(
            Organization(id=ObjectId(auth_result), name=auth_result)
            if isinstance(auth_result, str)
            else auth_result,
            folder,
            None
            if parent_folder_org_id is None
            else NoteFolder(
                id=ObjectId("000000000000000000000003"),
                name="Parent Folder",
                organization_id=parent_folder_org_id,
                parent_id=None,
            ),
        )
    assert exc_info.value.status_code == expected_status_code
    assert expected_text_pattern in str(exc_info.value.detail)
