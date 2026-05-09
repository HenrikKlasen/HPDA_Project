import BuildingsMap from "../components/maps/BuildingsMap";
import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

function MapExplorerPage() {
  const [selectedObject, setSelectedObject] = useState(null);
  const [employers, setEmployers] = useState([]);
  const navigate = useNavigate();

  useEffect(() => {
    let data = localStorage.getItem("employers");
    if (!data) {
      fetch("http://localhost:5000/api/export/employer-health-csv")
        .then((res) => res.text())
        .then((data) => {
          localStorage.setItem("employers", data);
        })
        .catch((error) => {
          console.error("Failed to fetch business health content:", error);
        });
      data = localStorage.getItem("employers");
    }
    try {
      const parsed = JSON.parse(data);
      if (Array.isArray(parsed)) {
        setEmployers(parsed);
        console.log("Employers loaded:", parsed);
      } else {
        setSelectedObject(parsed);
      }
    } catch (e) {
      console.error("Failed to parse employers data:", e);
    }
  }, []);

  const handleObjectSelect = (pointData) => {
    console.log("Object selected:", pointData);

    if (pointData) {
      // 1. If it's an employer, try to get the rich data
      if (pointData.category === "Employer" && employers.length > 0) {
        let matchedEmployer = employers.find(
          (emp) => String(emp.employerId) === String(pointData.id),
        );

        if (matchedEmployer) {
          setSelectedObject({
            ...matchedEmployer,
            _type: "Employer",
          });
          return;
        }
      }

      // 2. If it's a building or any other point, just show its basic info
      setSelectedObject({
        ...pointData,
        _type: pointData.category || pointData.type || "Object",
      });
    }
  };

  return (
    <section>
      <div className="map-card large">
        <BuildingsMap onEmployerSelect={handleObjectSelect} />
      </div>
    </section>
  );
}

export default MapExplorerPage;
