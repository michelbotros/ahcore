"""This is an attempt to populate an ahcore manifest database using my own in-house LANS datset dataset."""
import os
import random
from pathlib import Path

from dlup import SlideImage
from dlup.experimental_backends import ImageBackend  # type: ignore

from ahcore.utils.database_models import (
    CategoryEnum,
    Image,
    ImageAnnotations,
    ImageLabels,
    Manifest,
    Mask,
    Patient,
    PatientLabels,
    Split,
    SplitDefinitions,
)
from ahcore.utils.manifest import open_db


def get_patient_code_from_lans_filepath(lans_filepath) -> str:
    return str(lans_filepath).split('/')[-1][:7]


def populate_from_folder(
    session,
    image_folder: Path
):
    print('Creating manifest file!')
    manifest = Manifest(name="first_500_he")
    session.add(manifest)
    session.flush()

    split_definition = SplitDefinitions(version="v1", description="Initial split")
    session.add(split_definition)
    session.flush()

    tiff_files = [f for f in sorted(image_folder.rglob("*.tiff")) if 'HE' in str(f)][:500]
    print('Found {} tiff files!'.format(len(tiff_files)))

    for file_path in tiff_files:
        patient_code = get_patient_code_from_lans_filepath(file_path)

        # Only add patient if it doesn't exist
        existing_patient = session.query(Patient).filter_by(patient_code=patient_code).first()  # type: ignore

        if existing_patient:
            patient = existing_patient
        else:
            patient = Patient(patient_code=patient_code, manifest=manifest)
            session.add(patient)
            session.flush()

            split_category = CategoryEnum.PREDICT

            split = Split(
                category=split_category,
                patient=patient,
                split_definition=split_definition,
            )
            session.add(split)
            session.flush()

        # Add only the label if it does not exist yet.
        existing_label = session.query(PatientLabels).filter_by(key="study", patient_id=patient.id).first()
        if not existing_label:
            patient_label = PatientLabels(key="study", value="LANS", patient=patient)
            session.add(patient_label)
            session.flush()

        with SlideImage.from_file_path(
            file_path, backend=ImageBackend.OPENSLIDE
        ) as slide:  # type: ignore
            mpp = slide.mpp
            width, height = slide.size
            image = Image(
                filename=str(file_path),
                mpp=mpp,
                height=height,
                width=width,
                reader="OPENSLIDE",
                patient=patient,
            )
        session.add(image)
        session.flush()  # Flush so that Image ID is populated for future records

        # Randomly decide if it's cancer or benign
        image_label = ImageLabels(
            key="tumor_type", value="cancer" if random.choice([True, False]) else "benign", image=image
        )
        session.add(image_label)
        session.commit()



if __name__ == "__main__":
    manifest_file = 'manifest.db'
    image_folder = Path("/data/archief/AMC-data/Barrett/LANS")
    with open_db("sqlite:///{}".format(manifest_file)) as session:
        populate_from_folder(session, image_folder)

    print('Created manifest file at: {}'.format(os.path.join(os.getcwd(), manifest_file)))