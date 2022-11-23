-- AlterTable
ALTER TABLE "Creator" ADD COLUMN     "disabled" BOOLEAN DEFAULT false;

-- AlterTable
ALTER TABLE "Link" ADD COLUMN     "disabled" BOOLEAN DEFAULT false;
